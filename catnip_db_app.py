import os
import json
import base64
from typing import List, Dict, Any, Optional

from pymongo import MongoClient
from pymongo.errors import PyMongoError
from bson import ObjectId

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
MAX_ROWS = int(os.getenv("MAX_ROWS", "500"))

CAMPAIGN_PATH = "kh.aca"  # testing file to always load

# Middle-pane columns
DISPLAY_FIELDS = ["producer", "file", "variable_type"]


# -----------------------------------------------------------------------------
# Mongo: one shared client/collection
# -----------------------------------------------------------------------------
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=1500)
collection = client[MONGO_DB][MONGO_COLLECTION]


def png_bytes_to_data_uri(png_bytes: bytes) -> str:
    """
    Convert PNG bytes to a data URI suitable for <img src="...">.
    """
    if not png_bytes:
        return ""
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{b64}"


def chunk_tiles(tiles: List[Dict[str, str]], cols: int = 3) -> List[List[Optional[Dict[str, str]]]]:
    """
    Convert a flat list into rows of length cols, padding with None.
    """
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

    def distinct_variable_names(self) -> List[str]:
        if not self.ok:
            return []
        try:
            names = self.collection.distinct("variable_name")
            names = [n for n in names if isinstance(n, str)]
            names.sort()
            return names
        except PyMongoError as e:
            self.last_error = f"{type(e).__name__}: {e}"
            self.ok = False
            return []

    def query_entries_for_variable(
        self,
        variable_name: str,
        fields: List[str],
        variable_type: str = "variable",
    ) -> List[Dict[str, str]]:
        """
        Middle pane rows: variable entries (default variable_type='variable').
        Includes _id so we can fetch full doc for details.
        """
        if not self.ok or not variable_name:
            return []

        proj = {f: 1 for f in fields}
        proj["_id"] = 1

        try:
            cursor = (
                self.collection
                .find({"variable_name": variable_name, "variable_type": variable_type}, proj)
                .limit(MAX_ROWS)
            )

            rows: List[Dict[str, str]] = []
            for doc in cursor:
                row: Dict[str, str] = {"_id": str(doc.get("_id", ""))}
                for f in fields:
                    v = doc.get(f, "")
                    row[f] = "" if v is None else str(v)
                rows.append(row)
            return rows
        except PyMongoError as e:
            self.last_error = f"{type(e).__name__}: {e}"
            self.ok = False
            return []

    def get_document_by_id(self, id_str: str) -> Dict[str, Any]:
        if not self.ok or not id_str:
            return {}

        try:
            doc = self.collection.find_one({"_id": ObjectId(id_str)})
            if not doc:
                return {}
            doc["_id"] = str(doc["_id"])
            return doc
        except Exception as e:
            self.last_error = f"{type(e).__name__}: {e}"
            self.ok = False
            return {}

    def get_image_tiles_for_variable_row(
        self,
        variable_name: str,
        producer: Optional[str],
        file: Optional[str],
    ) -> List[Dict[str, str]]:
        """
        For a selected VARIABLE row, find associated IMAGE docs:
          - variable_name matches
          - variable_type == 'image'
          - producer matches (if provided)
          - file matches (if provided)
        Then:
          - distinct visualization_name values
          - for each visualization_name, pick ONE image doc
          - use image_bytes to build a data URI
        """
        if not self.ok or not variable_name:
            return []

        query: Dict[str, Any] = {
            "variable_name": variable_name,
            "variable_type": "image",
        }
        if producer:
            query["producer"] = producer
        if file:
            query["file"] = file

        try:
            vis_names = self.collection.distinct("visualization_name", query)
            vis_names = [v for v in vis_names if isinstance(v, str) and v]
            vis_names.sort()

            tiles: List[Dict[str, str]] = []
            for vis in vis_names:
                doc = self.collection.find_one(
                    {**query, "visualization_name": vis},
                    {"_id": 0, "visualization_name": 1, "image_bytes": 1},
                    sort=[("_id", -1)],     # most recent / "last" inserted
                )
                if not doc:
                    continue

                img = doc.get("image_bytes", None)

                # PyMongo returns BSON Binary as a bytes-like object; bytes(img) is safe.
                src = ""
                if img:
                    try:
                        src = png_bytes_to_data_uri(bytes(img))
                    except Exception:
                        src = ""

                tiles.append(
                    {
                        "vis": vis,
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

state.tableFields = list(DISPLAY_FIELDS)
state.tableRows = []

# Right pane: details + images
state.detailsDoc = {}
state.detailsJson = ""

state.imageTiles = []
state.imageGrid = []
state.imageStatus = ""
state.selectedRowId = ""



def refresh_variable_list():
    state.variableNames = db.distinct_variable_names()
    state.dbOk = db.ok
    state.dbStatus = "Connected" if db.ok else f"DB error: {db.last_error}"


@ctrl.add("pick_var")
def pick_var(var_name: str, **_):
    state.selectedVar = var_name


@ctrl.add("show_details")
def show_details(row: Dict[str, str], **_):
    """
    Called when user clicks Details in middle pane.
    - Loads full doc for detailsJson (top-right)
    - Loads one image per visualization_name using image_bytes (bottom-right)
    """
    # Full doc -> details pane
    id_str = row.get("_id", "")
    doc = db.get_document_by_id(id_str)
    doc = doc['metadata'] if 'metadata' in doc else {}
    state.detailsDoc = doc
    state.detailsJson = json.dumps(doc, indent=2, default=str) if doc else ""

    # Associated images -> bottom pane
    variable_name = state.selectedVar
    producer = row.get("producer", None)
    file = row.get("file", None)

    tiles = db.get_image_tiles_for_variable_row(variable_name, producer, file)
    state.imageTiles = tiles
    state.imageGrid = chunk_tiles(tiles, cols=3)

    if not tiles:
        state.imageStatus = "No images found for this row."
    else:
        ok = sum(1 for t in tiles if t.get("status") == "ok")
        bad = len(tiles) - ok
        state.imageStatus = f"Images: {len(tiles)} (ok={ok}, missing-bytes={bad})"


@ctrl.add("select_row")
def select_row(row: Dict[str, str], **_):
    # highlight selection
    state.selectedRowId = row.get("_id", "")
    # populate right pane
    show_details(row)

@state.change("selectedVar")
def on_selected_var(selectedVar, **_):
    if not selectedVar:
        state.tableRows = []
        state.detailsDoc = {}
        state.detailsJson = ""
        state.imageTiles = []
        state.imageGrid = []
        state.imageStatus = ""
        return

    try:
        rows = db.query_entries_for_variable(selectedVar, state.tableFields, variable_type="variable")
    except Exception as e:
        state.tableRows = []
        state.dbOk = False
        state.dbStatus = f"Query failed: {type(e).__name__}: {e}"
        return

    state.dbOk = db.ok
    state.dbStatus = (
        f'Connected • "{selectedVar}" → {len(rows)} variable rows (up to {MAX_ROWS})'
        if db.ok
        else f'DB error • "{selectedVar}" • {db.last_error}'
    )
    state.tableRows = rows

    # Clear right pane when switching left variable
    state.selectedRowId = ""
    state.detailsDoc = {}
    state.detailsJson = ""
    state.imageTiles = []
    state.imageGrid = []
    state.imageStatus = ""


def ingest_campaign_every_time(**_kwargs):
    """
    Synchronous ingest for small test files.
    Called when the server is ready; Trame passes state as kwargs.
    """
    if not db.ok:
        state.dbOk = False
        state.dbStatus = f"DB error: {db.last_error}"
        return

    try:
        state.dbOk = True
        state.dbStatus = f"Loading {CAMPAIGN_PATH}..."

        # Avoid duplicates for this test file
        collection.delete_many({"campaign_path": CAMPAIGN_PATH})

        # Ingest
        parse_campaign(CAMPAIGN_PATH, collection)

        # Update UI
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

                # Middle: variable rows table (type='variable')
                with vuetify.VCol(cols=5):
                    with vuetify.VCard(variant="outlined"):
                        with vuetify.VCardTitle():
                            html.Div("Rows (variable_type='variable')")
                            vuetify.VSpacer()
                            html.Div("{{ tableRows.length }}", class_="text-caption")

                        with vuetify.VCardText(style="height: 80vh; overflow-y: auto;"):
                            with vuetify.VTable(density="compact"):
                                with html.Thead():
                                    with html.Tr():
                                        for f in DISPLAY_FIELDS:
                                            html.Th(f)

                                with html.Tbody():
                                    with vuetify.Template(v_for="item in tableRows", key="item._id"):
                                        with html.Tr(
                                            click=(ctrl.select_row, "[item]"),
                                            style="cursor: pointer;",
                                            v_bind_style=("item._id === selectedRowId ? { backgroundColor: 'rgba(0,0,0,0.06)' } : {}",),
                                        ):
                                            for f in DISPLAY_FIELDS:
                                                html.Td(f"{{{{ item['{f}'] }}}}")


                # Right: details (top) + images grid (bottom)
                with vuetify.VCol(cols=4):
                    with vuetify.VCard(variant="outlined"):
                        vuetify.VCardTitle("Details")
                        with vuetify.VCardText(style="height: 36vh; overflow-y: auto;"):
                            html.Div(
                                "{{ detailsDoc._id ? ('_id: ' + detailsDoc._id) : 'Click Details on a row' }}",
                                class_="text-caption mb-2",
                            )
                            html.Pre(
                                "{{ detailsJson }}",
                                style="white-space: pre-wrap; font-family: monospace;",
                            )

                    html.Div(style="height: 8px")

                    with vuetify.VCard(variant="outlined"):
                        with vuetify.VCardTitle():
                            html.Div("Images")
                            vuetify.VSpacer()
                            html.Div("{{ imageStatus }}", class_="text-caption")

                        with vuetify.VCardText(style="height: 42vh; overflow-y: auto;"):
                            with vuetify.VTable(density="compact"):
                                with html.Tbody():
                                    with vuetify.Template(v_for="(row, rIdx) in imageGrid", key="rIdx"):
                                        with html.Tr():
                                            with vuetify.Template(v_for="(tile, cIdx) in row", key="cIdx"):
                                                with html.Td(style="vertical-align: top; width: 33%;"):
                                                    with vuetify.Template(v_if="tile"):
                                                        html.Div("{{ tile.vis }}", class_="text-caption mb-1")
                                                        with vuetify.Template(v_if="tile.src"):
                                                            html.Img(
                                                                src=("tile.src",),
                                                                style="max-width: 100%; max-height: 200px; object-fit: contain;",
                                                            )
                                                        with vuetify.Template(v_else=True):
                                                            html.Div(
                                                                "No image_bytes",
                                                                class_="text-caption",
                                                                style="color: #b00020;",
                                                            )
                                                    with vuetify.Template(v_else=True):
                                                        html.Div("")

if __name__ == "__main__":
    server.start()
