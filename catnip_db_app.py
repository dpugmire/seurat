import os
import base64
import statistics
import ast
import subprocess
import tempfile
from typing import List, Dict, Any, Optional, Tuple

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from trame.app import get_server
from trame.ui.vuetify3 import SinglePageLayout
from trame.widgets import vuetify3 as vuetify
from trame.widgets import html

from ingest_campaign import parse_campaign  # parse_campaign(campaign_path, collection)

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "catnip_campaigns")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "campaign_entries")

CAMPAIGN_PATH = "kh.aca"  # testing file to always load

SOURCE_FIELDS = ["producer", "casename", "file", "min", "max"]
MAX_IMAGE_TILES = 4

# Movie (prototype): build mp4 in-memory and embed as data URI
MOVIE_FPS = int(os.getenv("MOVIE_FPS", "24"))
MAX_MOVIE_FRAMES = int(os.getenv("MAX_MOVIE_FRAMES", "240"))  # keep small-ish for now

# -----------------------------------------------------------------------------
# Mongo: one shared client/collection
# -----------------------------------------------------------------------------
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=1500)
collection = client[MONGO_DB][MONGO_COLLECTION]


def png_bytes_to_data_uri(png_bytes: bytes) -> str:
    if not png_bytes:
        return ""
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{b64}"


def mp4_bytes_to_data_uri(mp4_bytes: bytes) -> str:
    if not mp4_bytes:
        return ""
    b64 = base64.b64encode(mp4_bytes).decode("ascii")
    return f"data:video/mp4;base64,{b64}"


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        try:
            return float(str(value).strip())
        except Exception:
            return None


def _fmt(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{value:.6g}"
    except Exception:
        return str(value)


def chunk_tiles(tiles: List[Dict[str, Any]], cols: int) -> List[List[Optional[Dict[str, Any]]]]:
    rows: List[List[Optional[Dict[str, Any]]]] = []
    row: List[Optional[Dict[str, Any]]] = []
    for t in tiles:
        row.append(t)
        if len(row) == cols:
            rows.append(row)
            row = []
    if row:
        while len(row) < cols:
            row.append(None)
        rows.append(row)
    return rows


def frames_to_mp4_bytes(png_frames: List[bytes], fps: int = 24) -> bytes:
    """
    Lowest-friction prototype approach:
      - write frames to a temp dir as frame_000000.png ...
      - call ffmpeg to produce an mp4 (H.264) to a temp file
      - return mp4 bytes
    """
    if not png_frames:
        return b""

    if fps <= 0:
        fps = 24

    with tempfile.TemporaryDirectory(prefix="catnip_movie_") as tmpdir:
        # Write frames
        for i, b in enumerate(png_frames):
            fname = os.path.join(tmpdir, f"frame_{i:06d}.png")
            with open(fname, "wb") as f:
                f.write(b)

        out_mp4 = os.path.join(tmpdir, "movie.mp4")

        # -pix_fmt yuv420p increases compatibility with browsers
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-framerate",
            str(int(fps)),
            "-i",
            os.path.join(tmpdir, "frame_%06d.png"),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            out_mp4,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            raise RuntimeError(f"ffmpeg failed (code {result.returncode}): {stderr}")

        with open(out_mp4, "rb") as f:
            return f.read()


# -----------------------------------------------------------------------------
# Query parsing: restricted python-like boolean expression -> Mongo filter
# -----------------------------------------------------------------------------
FIELD_ALIASES = {
    "var": "variable_name",
    "type": "variable_type",
    "min": "min",
    "max": "max",
}

ALLOWED_FIELDS = {
    "variable_name",
    "variable_type",
    "producer",
    "casename",
    "file",
    "visualization_name",
    "variable_path",
    "campaign_path",
    "variable_location",
    "frame_index",
    "min",
    "max",
}


def _field_name(name: str) -> str:
    mapped = FIELD_ALIASES.get(name, name)
    if mapped not in ALLOWED_FIELDS:
        raise ValueError(f"Unknown/unsupported field: {name}")
    return mapped


def _const(node: ast.AST):
    if isinstance(node, ast.Constant):
        return node.value

    # allow unary +/- for numeric constants (e.g. -1.0)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        v = _const(node.operand)
        if not isinstance(v, (int, float)):
            raise ValueError("Unary +/- is only allowed on numeric constants")
        return +v if isinstance(node.op, ast.UAdd) else -v

    if isinstance(node, (ast.List, ast.Tuple)):
        return [_const(elt) for elt in node.elts]

    raise ValueError(f"Only constants/lists are allowed, got: {type(node).__name__}")


def python_query_to_mongo(expr: str) -> Dict[str, Any]:
    expr = (expr or "").strip()
    if not expr:
        return {}

    tree = ast.parse(expr, mode="eval")

    def compile_node(node: ast.AST) -> Dict[str, Any]:
        if isinstance(node, ast.BoolOp):
            op = "$and" if isinstance(node.op, ast.And) else "$or"
            parts = [compile_node(v) for v in node.values]
            flat: List[Dict[str, Any]] = []
            for p in parts:
                if isinstance(p, dict) and op in p and len(p) == 1:
                    flat.extend(p[op])
                else:
                    flat.append(p)
            return {op: flat}

        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            inner = compile_node(node.operand)
            return {"$nor": [inner]}

        if isinstance(node, ast.Compare):
            if len(node.ops) != 1 or len(node.comparators) != 1:
                raise ValueError("Chained comparisons are not supported")

            left = node.left
            op = node.ops[0]
            right = node.comparators[0]

            if not isinstance(left, ast.Name):
                raise ValueError("Left side must be a field name")

            field = _field_name(left.id)

            if isinstance(op, ast.Eq):
                return {field: _const(right)}
            if isinstance(op, ast.NotEq):
                return {field: {"$ne": _const(right)}}
            if isinstance(op, ast.In):
                return {field: {"$in": _const(right)}}
            if isinstance(op, ast.NotIn):
                return {field: {"$nin": _const(right)}}

            if isinstance(op, ast.Gt):
                return {field: {"$gt": _const(right)}}
            if isinstance(op, ast.GtE):
                return {field: {"$gte": _const(right)}}
            if isinstance(op, ast.Lt):
                return {field: {"$lt": _const(right)}}
            if isinstance(op, ast.LtE):
                return {field: {"$lte": _const(right)}}

            raise ValueError(f"Unsupported operator: {type(op).__name__}")

        if isinstance(node, ast.Name):
            field = _field_name(node.id)
            return {field: {"$ne": None}}

        raise ValueError(f"Unsupported expression: {type(node).__name__}")

    return compile_node(tree.body)


def _and_filter(base: Dict[str, Any], extra: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not extra:
        return base
    return {"$and": [base, extra]}


class CampaignDb:
    def __init__(self, collection):
        self.collection = collection
        self.ok = True
        self.last_error = ""

        try:
            _ = self.collection.database.client.admin.command("ping")
        except Exception as e:
            self.ok = False
            self.last_error = f"{type(e).__name__}: {e}"

    def distinct_variable_names(self, extra_filter: Optional[Dict[str, Any]] = None) -> List[str]:
        if not self.ok:
            return []
        try:
            base = {"variable_type": "variable"}
            query = _and_filter(base, extra_filter)
            names = self.collection.distinct("variable_name", query)
            names = [n for n in names if isinstance(n, str)]
            names.sort()
            return names
        except PyMongoError as e:
            self.last_error = f"{type(e).__name__}: {e}"
            self.ok = False
            return []

    def variable_min_max_summary(
        self,
        variable_name: str,
        extra_filter: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.ok or not variable_name:
            return {}

        base_query: Dict[str, Any] = {
            "variable_name": variable_name,
            "variable_type": "variable",
        }
        query = _and_filter(base_query, extra_filter)

        proj = {
            "_id": 0,
            "producer": 1,
            "casename": 1,
            "file": 1,
            "metadata": 1,
            "Min": 1,
            "Max": 1,
            "min": 1,
            "max": 1,
        }

        try:
            cursor = self.collection.find(query, proj)

            mins: List[float] = []
            maxs: List[float] = []
            num_sources = 0
            sources: List[Dict[str, Any]] = []

            for doc in cursor:
                num_sources += 1

                fmin = _to_float(doc.get("min", None))
                fmax = _to_float(doc.get("max", None))

                if fmin is None or fmax is None:
                    md = doc.get("metadata", {})
                    if not isinstance(md, dict):
                        md = {}
                    raw_min = md.get("Min", doc.get("Min", None))
                    raw_max = md.get("Max", doc.get("Max", None))
                    fmin = _to_float(raw_min) if fmin is None else fmin
                    fmax = _to_float(raw_max) if fmax is None else fmax

                if (fmin is not None) and (fmax is not None):
                    mins.append(fmin)
                    maxs.append(fmax)

                sources.append(
                    {
                        "producer": "" if doc.get("producer", None) is None else str(doc.get("producer")),
                        "casename": "" if doc.get("casename", None) is None else str(doc.get("casename")),
                        "file": "" if doc.get("file", None) is None else str(doc.get("file")),
                        "min": fmin,
                        "max": fmax,
                    }
                )

            valid = len(mins)

            return {
                "variable": variable_name,
                "num_sources": num_sources,
                "global_min": min(mins) if valid else None,
                "global_max": max(maxs) if valid else None,
                "mean_min": statistics.fmean(mins) if valid else None,
                "mean_max": statistics.fmean(maxs) if valid else None,
                "median_min": statistics.median(mins) if valid else None,
                "median_max": statistics.median(maxs) if valid else None,
                "sources": sources,
            }

        except Exception as e:
            self.last_error = f"{type(e).__name__}: {e}"
            self.ok = False
            return {}

    # --- Frame queries --------------------------------------------------------

    def get_movie_frames_for_stream(
        self,
        variable_name: str,
        visualization_name: str,
        producer: str,
        casename: str,
        file: str = "",
        extra_filter: Optional[Dict[str, Any]] = None,
        limit_frames: int = 240,
    ) -> Tuple[List[bytes], int]:
        """
        Return (frames, total_count) for ONE visualization stream, sorted by frame_index.
        """
        if not self.ok or not variable_name:
            return ([], 0)

        base_query: Dict[str, Any] = {
            "variable_name": variable_name,
            "variable_type": "image",
            "visualization_name": visualization_name,
            "producer": producer,
            "casename": casename,
        }
        if file:
            base_query["file"] = file

        query = _and_filter(base_query, extra_filter)

        proj = {
            "_id": 1,
            "image_bytes": 1,
            "frame_index": 1,
        }

        try:
            total = int(self.collection.count_documents(query))
            cursor = (
                self.collection
                .find(query, proj)
                .sort([("frame_index", 1), ("_id", 1)])
                .limit(int(limit_frames))
            )

            frames: List[bytes] = []
            for doc in cursor:
                img = doc.get("image_bytes", None)
                if img:
                    try:
                        frames.append(bytes(img))
                    except Exception:
                        continue

            return (frames, total)

        except Exception as e:
            self.last_error = f"{type(e).__name__}: {e}"
            self.ok = False
            return ([], 0)

    def get_first_movie_tiles_for_variable(
        self,
        variable_name: str,
        extra_filter: Optional[Dict[str, Any]] = None,
        limit: int = 4,
        limit_frames: int = 240,
        fps: int = 24,
    ) -> List[Dict[str, Any]]:
        """
        Return up to `limit` DISTINCT visualization streams as MOVIES.

        Distinctness key: (visualization_name, producer, casename, file)

        For each stream:
          - fetch frames (respecting QueryView via extra_filter)
          - build mp4 via ffmpeg
          - return tile with src=data:video/mp4;base64,...
        """
        if not self.ok or not variable_name:
            return []

        base_query: Dict[str, Any] = {
            "variable_name": variable_name,
            "variable_type": "image",
            "visualization_name": {"$ne": ""},
        }
        query = _and_filter(base_query, extra_filter)

        proj = {
            "_id": 1,
            "producer": 1,
            "casename": 1,
            "file": 1,
            "visualization_name": 1,
        }

        try:
            cursor = (
                self.collection
                .find(query, proj)
                .sort([("_id", 1)])
            )

            seen = set()
            tiles: List[Dict[str, Any]] = []

            for doc in cursor:
                vis = str(doc.get("visualization_name", "") or "")
                producer = str(doc.get("producer", "") or "")
                casename = str(doc.get("casename", "") or "")
                file = str(doc.get("file", "") or "")

                if not vis:
                    continue

                key = (vis, producer, casename, file)
                if key in seen:
                    continue
                seen.add(key)

                # fetch frames for this stream
                frames, total = self.get_movie_frames_for_stream(
                    variable_name,
                    visualization_name=vis,
                    producer=producer,
                    casename=casename,
                    file=file,
                    extra_filter=extra_filter,
                    limit_frames=limit_frames,
                )

                src = ""
                media_type = "video"
                status = "ok"
                note = ""

                if not frames:
                    status = "no-frames"
                    note = "no frames"
                elif len(frames) == 1:
                    src = png_bytes_to_data_uri(frames[0])
                    media_type = "image"
                    note = "1 frame (rendered as image)"
                else:
                    try:
                        mp4 = frames_to_mp4_bytes(frames, fps=fps)
                        src = mp4_bytes_to_data_uri(mp4)
                        if total > len(frames):
                            note = f"{len(frames)} of {total} frames"
                        else:
                            note = f"{len(frames)} frames"
                    except Exception as e:
                        status = "build-failed"
                        note = f"{type(e).__name__}: {e}"
                        src = ""

                # NOTE: keep a short label; details are shown via UI toggle now
                tiles.append(
                    {
                        "variable_name": variable_name,
                        "visualization_name": vis,
                        "producer": producer,
                        "casename": casename,
                        "file": file,
                        "src": src,
                        "media_type": media_type,
                        "status": status,
                        "note": note,
                    }
                )

                if len(tiles) >= int(limit):
                    break

            return tiles

        except Exception as e:
            self.last_error = f"{type(e).__name__}: {e}"
            self.ok = False
            return []


# -----------------------------------------------------------------------------
# Trame (Vue3)
# -----------------------------------------------------------------------------
server = get_server(client_type="vue3")
state, ctrl = server.state, server.controller

db = CampaignDb(collection)

# State init
state.dbOk = db.ok
state.dbStatus = "Connected" if db.ok else f"DB error: {db.last_error}"

state.variableNames = []
state.selectedVar = ""

# Query UI
state.queryText = ""
state.queryStatus = ""
state.queryError = ""
state.queryFilter = {}          # Mongo filter for QueryView
state.queryViewLabel = "ALL"    # Display label in panels

# Details panel fields
state.detailsSelectedVar = ""
state.detailsNumSources = 0

state.detailsGlobalMin = ""
state.detailsGlobalMax = ""
state.detailsMeanMin = ""
state.detailsMeanMax = ""
state.detailsMedianMin = ""
state.detailsMedianMax = ""

# Sources
state.showSources = False
state.sourceRows = []
state.sourceSortField = SOURCE_FIELDS[0]
state.sourceSortAsc = True

# Movies panel
state.movieTiles = []
state.movieStatus = ""

# NEW: per-visualization details toggle in Movies panel
# key: "vis|producer|casename|file" -> bool
state.movieDetailsOpen = {}


def refresh_variable_list():
    state.variableNames = db.distinct_variable_names(extra_filter=state.queryFilter or None)
    state.dbOk = db.ok
    state.dbStatus = "Connected" if db.ok else f"DB error: {db.last_error}"


def clear_details():
    state.detailsSelectedVar = ""
    state.detailsNumSources = 0
    state.detailsGlobalMin = ""
    state.detailsGlobalMax = ""
    state.detailsMeanMin = ""
    state.detailsMeanMax = ""
    state.detailsMedianMin = ""
    state.detailsMedianMax = ""

    state.showSources = False
    state.sourceRows = []
    state.sourceSortField = SOURCE_FIELDS[0]
    state.sourceSortAsc = True


def clear_right_panes():
    clear_details()
    state.movieTiles = []
    state.movieStatus = ""
   


def _movie_key(tile: Dict[str, Any]) -> str:
    vis = str(tile.get("visualization_name", "") or "")
    producer = str(tile.get("producer", "") or "")
    casename = str(tile.get("casename", "") or "")
    file = str(tile.get("file", "") or "")
    return f"{vis}|{producer}|{casename}|{file}"


def update_selected_var_panels(var_name: str):
    """
    Populate Details + Movies from the current QueryView (state.queryFilter).
    """
    if not var_name:
        clear_right_panes()
        return

    qf = state.queryFilter or None

    summary = db.variable_min_max_summary(var_name, extra_filter=qf)

    state.dbOk = db.ok
    state.dbStatus = (
        f'Connected • Selected variable: "{var_name}" • QueryView: {state.queryViewLabel}'
        if db.ok
        else f'DB error • "{var_name}" • {db.last_error}'
    )

    state.detailsSelectedVar = var_name
    state.detailsNumSources = int(summary.get("num_sources", 0))

    state.detailsGlobalMin = _fmt(summary.get("global_min", None))
    state.detailsGlobalMax = _fmt(summary.get("global_max", None))
    state.detailsMeanMin = _fmt(summary.get("mean_min", None))
    state.detailsMeanMax = _fmt(summary.get("mean_max", None))
    state.detailsMedianMin = _fmt(summary.get("median_min", None))
    state.detailsMedianMax = _fmt(summary.get("median_max", None))

    rows = summary.get("sources", []) or []
    state.sourceRows = [
        {
            "producer": r.get("producer", ""),
            "casename": r.get("casename", ""),
            "file": r.get("file", ""),
            "min": _fmt(r.get("min", None)),
            "max": _fmt(r.get("max", None)),
        }
        for r in rows
    ]

    state.showSources = False
    if state.sourceSortField:
        sort_sources(state.sourceSortField)

    # Movies: 4 distinct visualization streams
    try:
        tiles = db.get_first_movie_tiles_for_variable(
            var_name,
            extra_filter=qf,
            limit=4,
            limit_frames=MAX_MOVIE_FRAMES,
            fps=MOVIE_FPS,
        )
        state.movieTiles = tiles

        # NEW: reset detail-open map on variable change
        state.movieDetailsOpen = {}

        if not tiles:
            state.movieStatus = f"No movies found for this variable in QueryView: {state.queryViewLabel}"
            state.movieStatus = ""
        else:
            ok = sum(1 for t in tiles if t.get("status") == "ok" and t.get("src"))
            bad = len(tiles) - ok
            state.movieStatus = (
                f"xxxMovies: {len(tiles)} (ok={ok}, issues={bad}) • "
                f"{MOVIE_FPS} fps • limit_frames={MAX_MOVIE_FRAMES} • "
                f"QueryView: {state.queryViewLabel}"
            )
            state.movieStatus = ""
    except Exception as e:
        state.movieTiles = []
        state.movieDetailsOpen = {}
        state.movieStatus = f"Movie query/build failed: {type(e).__name__}: {e}"


@ctrl.add("pick_var")
def pick_var(var_name: str, **_):
    state.selectedVar = var_name


@ctrl.add("toggle_sources")
def toggle_sources(**_):
    state.showSources = not bool(state.showSources)


@ctrl.add("sort_sources")
def sort_sources(field: str, **_):
    if not field:
        return

    if state.sourceSortField == field:
        state.sourceSortAsc = not bool(state.sourceSortAsc)
    else:
        state.sourceSortField = field
        state.sourceSortAsc = True

    asc = bool(state.sourceSortAsc)
    rows = list(state.sourceRows or [])

    def keyfn(row: Dict[str, str]):
        v = row.get(field, "")
        if v is None:
            return ("__str__", "")
        s = str(v)

        if field in ("min", "max"):
            try:
                return ("__num__", float(s))
            except Exception:
                return ("__str__", s.lower())

        return ("__str__", s.lower())

    state.sourceRows = sorted(rows, key=keyfn, reverse=(not asc))


# NEW: per-movie Details button toggle
@ctrl.add("toggle_movie_details")
def toggle_movie_details(key: str, **_):
    k = str(key or "")
    current = bool((state.movieDetailsOpen or {}).get(k, False))
    state.movieDetailsOpen = {**(state.movieDetailsOpen or {}), k: (not current)}


@ctrl.add("run_query")
def run_query(**_):
    q = (state.queryText or "").strip()

    if not q:
        state.queryFilter = {}
        state.queryError = ""
        state.queryStatus = "Query cleared"
        state.queryViewLabel = "ALL"
        refresh_variable_list()

        if state.selectedVar and state.selectedVar not in (state.variableNames or []):
            state.selectedVar = ""
            clear_right_panes()
        else:
            update_selected_var_panels(state.selectedVar)
        return

    try:
        filt = python_query_to_mongo(q)
        state.queryFilter = filt
        state.queryError = ""
        state.queryStatus = "Query OK"
        state.queryViewLabel = q
    except Exception as e:
        state.queryFilter = {}
        state.queryError = f"{type(e).__name__}: {e}"
        state.queryStatus = "Query ERROR"
        state.queryViewLabel = "ALL"
        return

    refresh_variable_list()

    if state.selectedVar and state.selectedVar not in (state.variableNames or []):
        state.selectedVar = ""
        clear_right_panes()
    else:
        update_selected_var_panels(state.selectedVar)


@ctrl.add("clear_query")
def clear_query(**_):
    state.queryText = ""
    state.queryFilter = {}
    state.queryError = ""
    state.queryStatus = "Query cleared"
    state.queryViewLabel = "ALL"
    refresh_variable_list()

    if state.selectedVar and state.selectedVar not in (state.variableNames or []):
        state.selectedVar = ""
        clear_right_panes()
    else:
        update_selected_var_panels(state.selectedVar)


@state.change("selectedVar")
def on_selected_var(selectedVar, **_):
    if not selectedVar:
        clear_right_panes()
        state.dbOk = db.ok
        state.dbStatus = "Connected" if db.ok else f"DB error: {db.last_error}"
        return

    update_selected_var_panels(selectedVar)


def ingest_campaign_every_time(**_kwargs):
    if not db.ok:
        state.dbOk = False
        state.dbStatus = f"DB error: {db.last_error}"
        return

    try:
        state.dbOk = True
        state.dbStatus = f"Loading {CAMPAIGN_PATH}..."

        collection.drop()
        parse_campaign(CAMPAIGN_PATH, collection)

        refresh_variable_list()
        state.dbStatus = f"Loaded {CAMPAIGN_PATH} • variables={len(state.variableNames)}"
    except Exception as e:
        state.dbOk = False
        state.dbStatus = f"Load failed: {type(e).__name__}: {e}"


ctrl.on_server_ready.add(ingest_campaign_every_time)

# -----------------------------------------------------------------------------
# UI (Vuetify3)
# -----------------------------------------------------------------------------
with SinglePageLayout(server) as layout:
    layout.title.set_text("Catnip Campaign DB Viewer (Vue3)")

    with layout.toolbar:
        vuetify.VBtn(
            "Refresh variables",
            click=refresh_variable_list,
            variant="outlined",
            size="small",
        )
        vuetify.VSpacer()
        html.Div("{{ dbStatus }}", class_="text-caption")

    with layout.content:
        with vuetify.VContainer(fluid=True, class_="pa-2"):

            # Query row
            with vuetify.VCard(variant="outlined", class_="mb-2"):
                with vuetify.VCardText(class_="py-2"):
                    with html.Div(style="display: flex; align-items: center; gap: 10px; width: 100%;"):
                        html.Span("Query:", class_="text-body-2")
                        vuetify.VTextField(
                            v_model=("queryText",),
                            placeholder="e.g. var == 'omega' and producer == 'ns' and min > 1.0",
                            density="compact",
                            hide_details=True,
                            style="max-width: 560px;",
                        )
                        vuetify.VBtn(
                            "Query",
                            click=ctrl.run_query,
                            variant="outlined",
                            size="small",
                        )
                        vuetify.VBtn(
                            "Clear Query",
                            click=ctrl.clear_query,
                            variant="text",
                            size="small",
                        )
                        vuetify.VSpacer()
                        html.Span("{{ queryStatus }}", class_="text-caption")

                with vuetify.Template(v_if="queryError"):
                    with vuetify.VCardText(class_="pt-0"):
                        html.Div("{{ queryError }}", class_="text-caption", style="color: #b00020;")

            vuetify.VAlert(
                "{{ dbStatus }}",
                type=("dbOk ? 'success' : 'error'",),
                variant="outlined",
                density="compact",
                class_="mb-2",
            )

            with vuetify.VRow():
                # Left: variable list
                with vuetify.VCol(cols=3):
                    with vuetify.VCard(variant="outlined"):
                        with vuetify.VCardTitle():
                            html.Div("Variables")
                            vuetify.VSpacer()
                            html.Div("{{ 'View: ' + queryViewLabel }}", class_="text-caption")
                        with vuetify.VCardText(style="height: 80vh; overflow-y: auto;"):
                            with vuetify.VList(density="compact"):
                                with vuetify.Template(v_for="v in variableNames", key="v"):
                                    vuetify.VListItem(
                                        title=("v",),
                                        active=("v === selectedVar",),
                                        click=(ctrl.pick_var, "[v]"),
                                    )

                # Right: details (top) + movies (bottom)
                with vuetify.VCol(cols=9):
                    with vuetify.VCard(variant="outlined"):
                        with vuetify.VCardTitle():
                            with html.Div(style="display: flex; align-items: center; gap: 12px; width: 100%;"):
                                html.Div("{{ detailsSelectedVar ? ('Details: ' + detailsSelectedVar) : 'Details' }}")

                                with vuetify.Template(v_if="detailsSelectedVar"):
                                    vuetify.VBtn(
                                        "{{ 'SOURCES(' + detailsNumSources + ')' }}",
                                        variant="text",
                                        size="small",
                                        click=ctrl.toggle_sources,
                                    )
                                    vuetify.VIcon(
                                        ("showSources ? 'mdi-chevron-up' : 'mdi-chevron-down'",),
                                        size="small",
                                    )

                                vuetify.VSpacer()
                                html.Div("{{ 'QueryView: ' + queryViewLabel }}", class_="text-caption")

                        with vuetify.VCardText(style="height: 36vh; overflow-y: auto;"):
                            with vuetify.Template(v_if="detailsSelectedVar"):
                                with vuetify.VRow(dense=True):
                                    with vuetify.VCol(cols=5):
                                        with vuetify.VTable(density="compact"):
                                            with html.Thead():
                                                with html.Tr():
                                                    html.Th("")
                                                    html.Th("Min")
                                                    html.Th("Max")
                                            with html.Tbody():
                                                with html.Tr():
                                                    html.Td("Global")
                                                    html.Td("{{ detailsGlobalMin }}")
                                                    html.Td("{{ detailsGlobalMax }}")
                                                with html.Tr():
                                                    html.Td("Median")
                                                    html.Td("{{ detailsMedianMin }}")
                                                    html.Td("{{ detailsMedianMax }}")
                                                with html.Tr():
                                                    html.Td("Mean")
                                                    html.Td("{{ detailsMeanMin }}")
                                                    html.Td("{{ detailsMeanMax }}")

                                    with vuetify.VCol(cols=7):
                                        with vuetify.Template(v_if="showSources"):
                                            with html.Div(
                                                style=(
                                                    "max-height: 30vh;"
                                                    "overflow-y: auto;"
                                                    "overflow-x: scroll;"
                                                    "white-space: nowrap;"
                                                    "scrollbar-gutter: stable;"
                                                )
                                            ):
                                                with vuetify.VTable(density="compact"):
                                                    with html.Thead():
                                                        with html.Tr():
                                                            for f in SOURCE_FIELDS:
                                                                with html.Th(
                                                                    style="cursor: pointer; user-select: none; white-space: nowrap;",
                                                                    click=(ctrl.sort_sources, f"['{f}']"),
                                                                ):
                                                                    html.Span(f)
                                                                    with vuetify.Template(v_if=(f"sourceSortField === '{f}'",)):
                                                                        vuetify.VIcon(
                                                                            ("sourceSortAsc ? 'mdi-arrow-up' : 'mdi-arrow-down'",),
                                                                            size="x-small",
                                                                            class_="ml-1",
                                                                        )
                                                                    with vuetify.Template(v_else=True):
                                                                        vuetify.VIcon(
                                                                            "mdi-sort",
                                                                            size="x-small",
                                                                            class_="ml-1",
                                                                        )
                                                    with html.Tbody():
                                                        with vuetify.Template(v_for="(r, i) in sourceRows", key="i"):
                                                            with html.Tr():
                                                                html.Td("{{ r.producer }}", style="white-space: nowrap;")
                                                                html.Td("{{ r.casename }}", style="white-space: nowrap;")
                                                                html.Td("{{ r.file }}", style="white-space: nowrap;")
                                                                html.Td("{{ r.min }}", style="white-space: nowrap;")
                                                                html.Td("{{ r.max }}", style="white-space: nowrap;")
                                        with vuetify.Template(v_else=True):
                                            html.Div("Sources table.", class_="text-caption")
                            with vuetify.Template(v_else=True):
                                html.Div("Select a variable", class_="text-caption")

                    html.Div(style="height: 8px")

                    # -----------------------------------------------------------------
                    # Movies panel (UPDATED LAYOUT)
                    # -----------------------------------------------------------------
                    with vuetify.VCard(variant="outlined"):
                        with vuetify.VCardTitle():
                            html.Div("Visualizations")
                            vuetify.VSpacer()
                            html.Div("{{ movieStatus }}", class_="text-caption")
                        with vuetify.VCardText(style="height: 42vh; overflow-y: auto;"):
                            with vuetify.Template(v_if="movieTiles.length"):
                                with vuetify.VRow(dense=True):
                                    with vuetify.Template(v_for="(tile, i) in movieTiles", key="i"):
                                        # 3 columns on desktop
                                        with vuetify.VCol(cols="12", sm="6", md="4", class_="pa-1"):
                                            with vuetify.VCardTitle(class_="pa-1"):
                                                with html.Div(style="display:flex; align-items:center; gap:8px; width:100%;"):
                                                    html.Div(
                                                        "{{ tile.visualization_name || 'visualization' }}",
                                                        style="flex:1; min-width:0; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;",
                                                    )
                                                    vuetify.VBtn(
                                                        "DETAILS",
                                                        size="x-small",
                                                        variant="tonal",
                                                        class_="ml-1",
                                                        click=(
                                                            ctrl.toggle_movie_details,
                                                            "[ (tile.visualization_name || '') + '|' + (tile.producer || '') + '|' + (tile.casename || '') + '|' + (tile.file || '') ]",
                                                        ),
                                                    )

                                                # Movie preview (smaller)
                                                with vuetify.VCardText(class_="pt-0 pb-1"):
                                                    with vuetify.Template(v_if="tile.src"):
                                                        with vuetify.Template(v_if="tile.media_type === 'image'"):
                                                            html.Img(
                                                                src=("tile.src",),
                                                                style=(
                                                                    "display:block;"
                                                                    "width: 100%;"
                                                                    "height: 240px;"  # <- smaller overall
                                                                    "object-fit: cover;"  # <- fills the box; crops if needed
                                                                    "border-radius: 4px;"
                                                                    "background: transparent;"
                                                                ),
                                                            )
                                                        with vuetify.Template(v_else=True):
                                                            html.Video(
                                                                src=("tile.src",),
                                                                controls=True,
                                                                autoplay=False,
                                                                loop=True,
                                                                muted=True,
                                                                style=(
                                                                    "display:block;"
                                                                    "width: 100%;"
                                                                    "height: 240px;"  # <- smaller overall
                                                                    "object-fit: cover;"  # <- fills the box; crops if needed
                                                                    "border-radius: 4px;"
                                                                    "background: transparent;"
                                                                ),
                                                            )

                                                    with vuetify.Template(v_else=True):
                                                        html.Div(
                                                            "{{ tile.note ? tile.note : 'No movie src' }}",
                                                            class_="text-caption",
                                                            style="color: #b00020;",
                                                        )

                                                # Expandable details
                                                with vuetify.VExpandTransition():
                                                    with vuetify.VCardText(
                                                        class_="pt-0",
                                                        v_show=(
                                                            "movieDetailsOpen[(tile.visualization_name || '') + '|' + (tile.producer || '') + '|' + (tile.casename || '') + '|' + (tile.file || '')]"
                                                        ),
                                                    ):
                                                        with vuetify.VTable(density="compact"):
                                                            with html.Tbody():
                                                                with html.Tr():
                                                                    html.Td("producer", class_="text-caption font-weight-medium", style="width: 160px;")
                                                                    html.Td("{{ tile.producer }}", class_="text-caption")
                                                                with html.Tr():
                                                                    html.Td("casename", class_="text-caption font-weight-medium")
                                                                    html.Td("{{ tile.casename }}", class_="text-caption")
                                                                with html.Tr():
                                                                    html.Td("file", class_="text-caption font-weight-medium")
                                                                    html.Td("{{ tile.file }}", class_="text-caption")
                                                                with html.Tr():
                                                                    html.Td("status", class_="text-caption font-weight-medium")
                                                                    html.Td("{{ tile.status }}", class_="text-caption")
                                                                with html.Tr():
                                                                    html.Td("note", class_="text-caption font-weight-medium")
                                                                    html.Td("{{ tile.note }}", class_="text-caption")
                            with vuetify.Template(v_else=True):
                                html.Div("Select a variable to begin.", class_="text-caption", v_if="!selectedVar")
                                html.Div("No movies in this QueryView.", class_="text-caption", v_else=True)



if __name__ == "__main__":
    server.start()
