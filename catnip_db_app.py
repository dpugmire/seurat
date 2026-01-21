import os
import base64
import statistics
import ast
from typing import List, Dict, Any, Optional

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


def chunk_tiles(tiles: List[Dict[str, str]], cols: int) -> List[List[Optional[Dict[str, str]]]]:
    rows: List[List[Optional[Dict[str, str]]]] = []
    row: List[Optional[Dict[str, str]]] = []
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


# -----------------------------------------------------------------------------
# Query parsing: restricted python-like boolean expression -> Mongo filter
# -----------------------------------------------------------------------------
FIELD_ALIASES = {
    "var": "variable_name",
    "type": "variable_type",
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
}

def _field_name(name: str) -> str:
    mapped = FIELD_ALIASES.get(name, name)
    if mapped not in ALLOWED_FIELDS:
        raise ValueError(f"Unknown/unsupported field: {name}")
    return mapped

def _const(node: ast.AST):
    if isinstance(node, ast.Constant):
        return node.value
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

            raise ValueError(f"Unsupported operator: {type(op).__name__}")

        if isinstance(node, ast.Name):
            field = _field_name(node.id)
            return {field: {"$ne": None}}

        raise ValueError(f"Unsupported expression: {type(node).__name__}")

    return compile_node(tree.body)


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
            query: Dict[str, Any] = {"variable_type": "variable"}
            if extra_filter:
                query = {"$and": [query, extra_filter]}

            names = self.collection.distinct("variable_name", query)
            names = [n for n in names if isinstance(n, str)]
            names.sort()
            return names
        except PyMongoError as e:
            self.last_error = f"{type(e).__name__}: {e}"
            self.ok = False
            return []

    def variable_min_max_summary(self, variable_name: str) -> Dict[str, Any]:
        if not self.ok or not variable_name:
            return {}

        query: Dict[str, Any] = {
            "variable_name": variable_name,
            "variable_type": "variable",
        }

        proj = {
            "_id": 0,
            "producer": 1,
            "casename": 1,
            "file": 1,
            "metadata": 1,
            "Min": 1,
            "Max": 1,
        }

        try:
            cursor = self.collection.find(query, proj)

            mins: List[float] = []
            maxs: List[float] = []
            num_sources = 0
            sources: List[Dict[str, Any]] = []

            for doc in cursor:
                num_sources += 1

                md = doc.get("metadata", {})
                if not isinstance(md, dict):
                    md = {}

                raw_min = md.get("Min", doc.get("Min", None))
                raw_max = md.get("Max", doc.get("Max", None))

                fmin = _to_float(raw_min)
                fmax = _to_float(raw_max)

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

    def get_first_image_tiles_for_variable(self, variable_name: str, limit: int = 4) -> List[Dict[str, str]]:
        if not self.ok or not variable_name:
            return []

        query: Dict[str, Any] = {
            "variable_name": variable_name,
            "variable_type": "image",
        }

        proj = {
            "_id": 1,
            "producer": 1,
            "casename": 1,
            "file": 1,
            "visualization_name": 1,
            "image_bytes": 1,
        }

        try:
            cursor = (
                self.collection
                .find(query, proj)
                .sort([("_id", 1)])
                .limit(int(limit))
            )

            tiles: List[Dict[str, str]] = []
            for doc in cursor:
                vis = doc.get("visualization_name", "")
                producer = doc.get("producer", "")
                casename = doc.get("casename", "")
                file = doc.get("file", "")

                label_parts = []
                if vis:
                    label_parts.append(str(vis))
                if producer:
                    label_parts.append(str(producer))
                if casename:
                    label_parts.append(str(casename))
                if file:
                    label_parts.append(str(file))

                label = " • ".join(label_parts) if label_parts else "image"

                img = doc.get("image_bytes", None)
                src = ""
                if img:
                    try:
                        src = png_bytes_to_data_uri(bytes(img))
                    except Exception:
                        src = ""

                tiles.append(
                    {
                        "label": label,
                        "src": src,
                        "status": "ok" if src else "no-bytes",
                    }
                )

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
state.queryFilter = {}

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

# Images panel
state.imageTiles = []
state.imageGrid = []
state.imageStatus = ""


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
    state.imageTiles = []
    state.imageGrid = []
    state.imageStatus = ""


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


@ctrl.add("run_query")
def run_query(**_):
    q = (state.queryText or "").strip()

    if not q:
        state.queryFilter = {}
        state.queryError = ""
        state.queryStatus = "Query cleared"
        refresh_variable_list()

        if state.selectedVar and state.selectedVar not in (state.variableNames or []):
            state.selectedVar = ""
            clear_right_panes()
        return

    try:
        filt = python_query_to_mongo(q)
        state.queryFilter = filt
        state.queryError = ""
        state.queryStatus = "Query OK"
    except Exception as e:
        state.queryFilter = {}
        state.queryError = f"{type(e).__name__}: {e}"
        state.queryStatus = "Query ERROR"
        return

    refresh_variable_list()

    if state.selectedVar and state.selectedVar not in (state.variableNames or []):
        state.selectedVar = ""
        clear_right_panes()


@ctrl.add("clear_query")
def clear_query(**_):
    # Reset textbox + clear applied filter + refresh variable list
    state.queryText = ""
    state.queryFilter = {}
    state.queryError = ""
    state.queryStatus = "Query cleared"
    refresh_variable_list()

    if state.selectedVar and state.selectedVar not in (state.variableNames or []):
        state.selectedVar = ""
        clear_right_panes()


@state.change("selectedVar")
def on_selected_var(selectedVar, **_):
    if not selectedVar:
        clear_right_panes()
        state.dbOk = db.ok
        state.dbStatus = "Connected" if db.ok else f"DB error: {db.last_error}"
        return

    summary = db.variable_min_max_summary(selectedVar)

    state.dbOk = db.ok
    state.dbStatus = (
        f'Connected • Selected variable: "{selectedVar}"'
        if db.ok
        else f'DB error • "{selectedVar}" • {db.last_error}'
    )

    state.detailsSelectedVar = selectedVar
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

    tiles = db.get_first_image_tiles_for_variable(selectedVar, limit=MAX_IMAGE_TILES)
    state.imageTiles = tiles
    state.imageGrid = chunk_tiles(tiles, cols=2)

    if not tiles:
        state.imageStatus = "No images found for this variable."
    else:
        ok = sum(1 for t in tiles if t.get("status") == "ok")
        bad = len(tiles) - ok
        state.imageStatus = f"Images: {len(tiles)} (ok={ok}, missing-bytes={bad})"


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
                            placeholder="e.g. var == 'omega' and producer == 'ns'",
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
                        vuetify.VCardTitle("Variables")
                        with vuetify.VCardText(style="height: 80vh; overflow-y: auto;"):
                            with vuetify.VList(density="compact"):
                                with vuetify.Template(v_for="v in variableNames", key="v"):
                                    vuetify.VListItem(
                                        title=("v",),
                                        active=("v === selectedVar",),
                                        click=(ctrl.pick_var, "[v]"),
                                    )

                # Right: details (top) + images (bottom)
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

                    with vuetify.VCard(variant="outlined"):
                        with vuetify.VCardTitle():
                            html.Div("Images")
                            vuetify.VSpacer()
                            html.Div("{{ imageStatus }}", class_="text-caption")

                        with vuetify.VCardText(style="height: 42vh; overflow-y: auto;"):
                            with vuetify.Template(v_if="imageTiles.length"):
                                with vuetify.VTable(density="compact"):
                                    with html.Tbody():
                                        with vuetify.Template(v_for="(row, rIdx) in imageGrid", key="rIdx"):
                                            with html.Tr():
                                                with vuetify.Template(v_for="(tile, cIdx) in row", key="cIdx"):
                                                    with html.Td(style="vertical-align: top; width: 50%;"):
                                                        with vuetify.Template(v_if="tile"):
                                                            html.Div("{{ tile.label }}", class_="text-caption mb-1")
                                                            with vuetify.Template(v_if="tile.src"):
                                                                html.Img(
                                                                    src=("tile.src",),
                                                                    style="max-width: 100%; max-height: 260px; object-fit: contain;",
                                                                )
                                                            with vuetify.Template(v_else=True):
                                                                html.Div(
                                                                    "No image_bytes",
                                                                    class_="text-caption",
                                                                    style="color: #b00020;",
                                                                )
                                                        with vuetify.Template(v_else=True):
                                                            html.Div("")
                            with vuetify.Template(v_else=True):
                                html.Div("Select a variable to begin.", class_="text-caption", v_if="!selectedVar")
                                html.Div("No images (yet).", class_="text-caption", v_else=True)


if __name__ == "__main__":
    server.start()
