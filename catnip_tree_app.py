#!/usr/bin/env python3

from trame.app import get_server
from trame.ui.vuetify3 import SinglePageLayout
from trame.widgets import vuetify3 as v3, html

# -----------------------------------------------------------------------------
# Data -> Tree utilities
# -----------------------------------------------------------------------------

def build_tree_from_paths(path_list):
    """
    Build a Vuetify3 VTreeview-compatible items structure from a list of
    'a/b/c' path strings.

    Each node has:
        - id:   full path up to that level (used as item_value)
        - name: label shown in the tree (segment name)
        - path: full path (for convenience)
        - children: list of children (if any)
    """
    root = {}

    for p in path_list:
        parts = p.split("/")
        current = root
        current_path = ""
        for part in parts:
            current_path = part if not current_path else f"{current_path}/{part}"
            if part not in current:
                current[part] = {
                    "__path__": current_path,
                    "__children__": {},
                }
            current = current[part]["__children__"]

    def to_items(level_dict):
        items = []
        for name in sorted(level_dict.keys()):
            info = level_dict[name]
            children_items = to_items(info["__children__"])
            item = {
                "id": info["__path__"],   # we use full path as the ID
                "name": name,             # label in the tree
                "path": info["__path__"], # keep full path as metadata
            }
            if children_items:
                item["children"] = children_items
            items.append(item)
        return items

    return to_items(root)


# Example paths (eventually replace with DB-driven list)
EXAMPLE_PATHS = [
    "campaignFile0/DataFile0/temp",
    "campaignFile0/DataFile0/pressure",
    "campaignFile0/DataFile0/velocity",
    "campaignFile0/DataFile1/temp",
    "campaignFile0/DataFile1/pressure",
    "campaignFile0/DataFile1/velocity",
    "campaignFile1/DataFile0/sensor0",
    "campaignFile1/DataFile0/sensor1",
]

# -----------------------------------------------------------------------------
# Trame setup
# -----------------------------------------------------------------------------

server = get_server()
server.client_type = "vue3"  # important for vuetify3

state = server.state

# Precompute tree items
state.tree_items = build_tree_from_paths(EXAMPLE_PATHS)

# Tree state
state.tree_opened = []          # list of opened item ids -> start fully collapsed
state.tree_activated = []       # list of activated (clicked) item ids
state.selection_details = "Nothing selected yet."


# Callback when *any* node is clicked/activated
@state.change("tree_activated")
def on_tree_activated(tree_activated, **kwargs):
    """
    Called whenever the VTreeview activated nodes change.

    tree_activated: list of activated item 'id's (we set these to full paths).
    """
    print("tree_activated changed:", tree_activated)

    if not tree_activated:
        state.selection_details = "Nothing selected."
        return

    last = tree_activated[-1]
    parts = last.split("/")
    depth = len(parts)
    if depth == 1:
        node_type = "CampaignFile"
    elif depth == 2:
        node_type = "DataFile"
    elif depth == 3:
        node_type = "Variable"
    else:
        node_type = f"Depth {depth}"

    state.selection_details = (
        f"Activated (clicked) node type: {node_type}\n"
        f"Full path: {last}\n"
        f"All activated IDs: {tree_activated}"
    )

# -----------------------------------------------------------------------------
# UI
# -----------------------------------------------------------------------------

with SinglePageLayout(server) as layout:
    layout.title.set_text("CatNip Campaign Tree")

    # Top toolbar
    with layout.toolbar:
        v3.VToolbarTitle("CatNip Campaign Tree")
        v3.VSpacer()
        v3.VBtn("Quit", icon="mdi-close", variant="text", click=server.stop)

    # Main content: left tree, right details
    with layout.content:
        with v3.VContainer(fluid=True, class_="pa-2"):
            with v3.VRow():
                # Left: tree
                with v3.VCol(cols=4):
                    with v3.VCard(elevation=2):
                        v3.VCardTitle("Campaign Browser")
                        with v3.VCardText():
                            v3.VTreeview(
                                # Tree data
                                items=("tree_items",),
                                item_title="name",
                                item_value="id",
                                item_children="children",

                                # Open state binding (Vuetify3: v-model:opened)
                                v_model_opened=("tree_opened", []),

                                # Activation binding (Vuetify3: v-model:activated)
                                v_model_activated=("tree_activated", []),
                                activatable=True,

                                # This flag expands when clicked. If off, it only expands when click on the arrow.
                                #open_on_click=True,

                                density="compact",
                            )

                # Right: selection details
                with v3.VCol(cols=8):
                    with v3.VCard(elevation=2):
                        v3.VCardTitle("Selection Details (Activated Node)")
                        with v3.VCardText():
                            html.Pre(
                                "{{ selection_details }}",
                                style="white-space: pre-wrap; font-family: monospace;",
                            )

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    server.start()
