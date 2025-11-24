#!/usr/bin/env python

from trame.app import get_server
from trame.ui.vuetify3 import SinglePageLayout
from trame.widgets import vuetify3 as v3
from trame.widgets import html

# -------------------------------------------------------------------------
# Sample data: flat paths like you described
# -------------------------------------------------------------------------
PATH_STRINGS = [
    "campaignFile0/DataFile0/temp",
    "campaignFile0/DataFile0/pressure",
    "campaignFile0/DataFile0/velocity",
    "campaignFile0/DataFile1/temp",
    "campaignFile0/DataFile1/pressure",
    "campaignFile0/DataFile1/velocity",
    "campaignFile1/DataFile0/sensor0",
    "campaignFile1/DataFile0/sensor1",
]


def build_tree_from_paths(paths, sep="/"):
    """
    Convert a list of path strings like:
        campaignFile0/DataFile0/temp
    into a nested structure suitable for VTreeview.

    Each node has:
      - id: full path (unique)
      - label: the current segment
      - path: full path
      - children: list of child nodes (if any)
    """
    root = {}

    for p in paths:
        parts = [part for part in p.split(sep) if part]
        current_level = root
        for depth, part in enumerate(parts):
            if part not in current_level:
                current_level[part] = {
                    "label": part,
                    "path": sep.join(parts[: depth + 1]),
                    "children": {},
                }
            current_level = current_level[part]["children"]

    def to_list(level_dict):
        nodes = []
        for key, entry in level_dict.items():
            children_list = to_list(entry["children"])
            node = {
                "id": entry["path"],   # what VTreeview will use as value
                "label": entry["label"],
                "path": entry["path"],
            }
            if children_list:
                node["children"] = children_list
            nodes.append(node)
        return nodes

    return to_list(root)


# -------------------------------------------------------------------------
# Trame setup
# -------------------------------------------------------------------------
server = get_server()
state, ctrl = server.state, server.controller

# Build tree once at startup
state.tree_items = build_tree_from_paths(PATH_STRINGS)

# Selection state (VTreeview uses a list of selected ids)
state.selected_nodes = []
state.current_path = ""
state.current_level = ""   # "campaign", "datafile", "variable"


@state.change("selected_nodes")
def on_tree_selection(selected_nodes, **kwargs):
    """Update info panel when the user selects something in the tree."""
    if not selected_nodes:
        state.current_path = ""
        state.current_level = ""
        return

    # Simple single-selection example: use the first selected id
    path = selected_nodes[0]
    state.current_path = path

    depth = len([p for p in path.split("/") if p])
    if depth == 1:
        state.current_level = "CampaignFile"
    elif depth == 2:
        state.current_level = "DataFile"
    elif depth == 3:
        state.current_level = "Variable"
    else:
        state.current_level = f"Depth {depth}"


# -------------------------------------------------------------------------
# UI layout
# -------------------------------------------------------------------------
with SinglePageLayout(server) as layout:
    layout.title.set_text("Campaign Browser")

    # Top toolbar (you can add controls here later)
    with layout.toolbar:
        v3.VToolbarTitle("Campaign Browser")
        v3.VSpacer()

    # Main content: left tree, right detail panel
    with layout.content:
        with v3.VContainer(fluid=True, classes="pa-2 fill-height"):
            with v3.VRow(classes="fill-height"):
                # Left: Tree view
                with v3.VCol(cols=4, classes="fill-height"):
                    with v3.VCard(classes="fill-height d-flex flex-column"):
                        v3.VCardTitle("Campaign / Datafile / Variable")
                        with v3.VCardText(classes="py-0 flex-grow-1 overflow-auto"):
                            v3.VTreeview(
                                # Data
                                items=("tree_items",),
                                # Selection
                                v_model_selected=("selected_nodes", []),
                                # Tell VTreeview how to read our item structure
                                item_title="label",
                                item_value="id",
                                item_children="children",
                                # UX options
                                activatable=True,
                                hoverable=True,
                                open_all=True,
                                dense=True,
                                shaped=True,
                            )

                # Right: Detail / info area
                with v3.VCol(cols=8, classes="fill-height"):
                    with v3.VCard(classes="fill-height d-flex flex-column"):
                        v3.VCardTitle("Selection Details")
                        with v3.VCardText(classes="flex-grow-1 overflow-auto"):
                            # Use safe HTML to get bold and code without multiple children
                            html.P(
                                "Level: <strong>{{ current_level }}</strong>",
                                safe=True,
                            )
                            html.P(
                                "Full path: <code>{{ current_path }}</code>",
                                safe=True,
                            )
                            html.Hr()
                            html.P(
                                "You can use `current_path` to drive plots, "
                                "table views, or RPC calls into your Mongo/ADIOS stack."
                            )

# -------------------------------------------------------------------------
# Start the app
# -------------------------------------------------------------------------
if __name__ == "__main__":
    server.start()
