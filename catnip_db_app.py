import os
from typing import List, Dict

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
MAX_ROWS = int(os.getenv("MAX_ROWS", "500"))

CAMPAIGN_PATH = "kh.aca"  # testing file to always load
DISPLAY_FIELDS = ["producer", "file", "variable_type"]

# -----------------------------------------------------------------------------
# Mongo: one shared client/collection
# -----------------------------------------------------------------------------
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=1500)
collection = client[MONGO_DB][MONGO_COLLECTION]


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

    def query_entries_for_variable(self, variable_name: str, fields: List[str], variable_type='variable') -> List[Dict[str, str]]:
        if not self.ok or not variable_name:
            return []

        proj = {f: 1 for f in fields}
        proj["_id"] = 0

        try:
            cursor = self.collection.find({"variable_name": variable_name, "variable_type": variable_type}, proj).limit(MAX_ROWS)
            rows: List[Dict[str, str]] = []
            for doc in cursor:
                row: Dict[str, str] = {}
                for f in fields:
                    v = doc.get(f, "")
                    row[f] = "" if v is None else str(v)
                rows.append(row)
            return rows
        except PyMongoError as e:
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
state.tableHeaders = [{"title": f, "key": f} for f in state.tableFields]  # Vuetify3
state.tableRows = []


def refresh_variable_list():
    print('meow')
    state.variableNames = db.distinct_variable_names()
    state.dbOk = db.ok
    state.dbStatus = "Connected" if db.ok else f"DB error: {db.last_error}"


@ctrl.add("pick_var")
def pick_var(var_name: str, **_):
    state.selectedVar = var_name


@state.change("selectedVar")
def on_selected_var(selectedVar, **_):
    if not selectedVar:
        state.tableRows = []
        return

    rows = db.query_entries_for_variable(selectedVar, state.tableFields)

    state.dbOk = db.ok
    state.dbStatus = (
        f'Connected • "{selectedVar}" → {len(rows)} rows (up to {MAX_ROWS})'
        if db.ok
        else f'DB error • "{selectedVar}" • {db.last_error}'
    )
    state.tableRows = rows


def ingest_campaign_every_time(**_kwargs):
    """
    Synchronous ingest, intended for small test files.
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
        print('status= ', state.dbStatus)
    except Exception as e:
        state.dbOk = False
        state.dbStatus = f"Load failed: {type(e).__name__}: {e}"


# Do the ingest after server is ready (prevents UI spinner during startup)
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
                        with vuetify.VCardText(style="height: 75vh; overflow-y: auto;"):
                            with vuetify.VList(density="compact"):
                                vuetify.VListItem(
                                    v_for="v in variableNames",
                                    key="v",
                                    title=("v",),
                                    active=("v === selectedVar",),
                                    click=(ctrl.pick_var, "[v]"),
                                )

                # Right: table
                with vuetify.VCol(cols=9):
                    with vuetify.VCard(variant="outlined"):
                        with vuetify.VCardTitle():
                            html.Div("Selected: ")
                            html.B("{{ selectedVar || '(none)' }}")
                            vuetify.VSpacer()
                            html.Div("Rows: {{ tableRows.length }}")

                        with vuetify.VCardText():
                            vuetify.VDataTable(
                                headers=("tableHeaders",),
                                items=("tableRows",),
                                items_per_page=25,
                                density="compact",
                            )

if __name__ == "__main__":
    server.start()
