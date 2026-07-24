"""Deterministic Trame application used by the browser tests."""

import argparse
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from seurat import module as seurat_module  # noqa: E402
from seurat.models.grid import empty_grid_cell  # noqa: E402
from seurat.state import init_state  # noqa: E402
from trame.app import get_server  # noqa: E402
from ui import build_ui  # noqa: E402


class FixtureDb:
    ok = True
    last_error = ""


def _image_source(color):
    return (
        "data:image/svg+xml;charset=utf-8,"
        f"%3Csvg xmlns='http://www.w3.org/2000/svg' width='64' height='64'%3E"
        f"%3Crect width='64' height='64' fill='{color.replace('#', '%23')}'/%3E"
        "%3C/svg%3E"
    )


def _plot_cell(mode):
    physical = mode == "physical"
    x_values = [0.0, 0.25, 1.0] if physical else list(range(80))
    y_values = (
        [10.0, 20.0, 30.0]
        if physical
        else [10.0 + (20.0 * index / 79.0) for index in range(80)]
    )
    cell = empty_grid_cell()
    cell.update(
        {
            "variable_id": "internal_energy",
            "variable_name": "internal_energy",
            "display_title": "internal_energy",
            "media_type": "plot1d",
            "status": "ok",
            "plot": {
                "x_label": "time" if physical else "step",
                "y_label": "internal_energy",
                "x_min": x_values[0],
                "x_max": x_values[-1],
                "y_min": 8.0,
                "y_max": 32.0,
                "data_x_min": x_values[0],
                "data_x_max": x_values[-1],
                "data_y_min": 10.0,
                "data_y_max": 30.0,
                "series": [
                    {
                        "x": x_values,
                        "y": y_values,
                        "source_label": "fixture",
                        "source_key": "fixture",
                        "color": "#1565c0",
                    }
                ],
            },
        }
    )
    return cell


def _image_sequence_cell(mode):
    physical = mode == "physical"
    frame_count = 3 if physical else 35
    colors = ("#c62828", "#2e7d32", "#1565c0")
    sources = [
        _image_source(colors[index % len(colors)]) for index in range(frame_count)
    ]
    cell = empty_grid_cell()
    cell.update(
        {
            "variable_id": "current_z",
            "variable_name": "current_z",
            "display_title": "current_z",
            "media_type": "image_sequence",
            "status": "ok",
            "src": sources[0],
            "fps": 2,
            "frame_count": len(sources),
            "frame_indices": list(range(frame_count)),
            "frame_sources": sources,
            "time_values": ([0.0, 0.25, 1.0] if physical else list(range(frame_count))),
            "time_mode": "physical_time" if physical else "timestep",
        }
    )
    return cell


def build_fixture_server(mode):
    server = get_server(f"seurat-browser-{mode}", client_type="vue3")
    server.enable_module(seurat_module)
    init_state(server.state, FixtureDb())

    state = server.state
    state.variableGroups = [
        {
            "name": "0D",
            "variables": [
                {
                    "id": "internal_energy",
                    "name": "internal_energy",
                    "label": "internal_energy",
                    "path": "fixture/scalars.bp/internal_energy",
                }
            ],
        },
        {
            "name": "2D",
            "variables": [
                {
                    "id": "current_z",
                    "name": "current_z",
                    "label": "current_z",
                    "path": "fixture/images/current_z",
                }
            ],
        },
    ]
    state.variableNames = ["internal_energy", "current_z"]
    state.variableLabelsById = {
        "internal_energy": "internal_energy",
        "current_z": "current_z",
    }
    state.variableGroupCollapsed = {"0D": False, "2D": False}
    state.variableGroupCollapsedByView = {
        "variables": dict(state.variableGroupCollapsed),
        "files": {},
    }
    state.gridRows = 1
    state.gridCols = 3
    state.gridSizingMode = "static"
    state.gridColumnSizes = [280, 280, 280]
    state.gridRowSizes = [352]
    state.gridColumnWeights = [1.0, 1.0, 1.0]
    state.gridRowWeights = [1.0]
    state.gridColumnTemplate = "280px 280px 280px"
    state.gridRowTemplate = "352px"
    state.gridFitColumnTemplate = " ".join(
        "minmax(180px, 1fr)" for _ in range(state.gridCols)
    )
    state.gridFitRowTemplate = "minmax(212px, 1fr)"
    state.gridCells = [_plot_cell(mode), _image_sequence_cell(mode), empty_grid_cell()]

    def toggle_variable_group(group_name):
        collapsed = dict(state.variableGroupCollapsed or {})
        collapsed[str(group_name)] = not bool(collapsed.get(str(group_name), False))
        state.variableGroupCollapsed = collapsed

    def pick_var(variable_id):
        picked = str(variable_id or "")
        if str(state.selectedVar or "") == picked:
            state.selectedVar = ""
            state.draggedVar = ""
            state.detailsSelectedVar = ""
            return
        state.selectedVar = picked
        state.draggedVar = picked
        state.detailsSelectedVar = picked
        state.detailsNumSources = 2
        state.detailsGlobalMin = "8"
        state.detailsGlobalMax = "32"
        state.detailsMedianMin = "10"
        state.detailsMedianMax = "30"
        state.detailsMeanMin = "11"
        state.detailsMeanMax = "29"
        state.queryViewLabel = "Variables"

    def set_active_grid_cell(cell_index, _ignored=0, _extend_selection=0):
        state.activeGridCell = int(cell_index)

    def assign_var_to_grid_cell(variable_id, cell_index):
        index = int(cell_index)
        cells = [dict(cell) for cell in state.gridCells]
        assigned = empty_grid_cell()
        assigned.update(
            {
                "variable_id": str(variable_id),
                "variable_name": str(variable_id),
                "display_title": str(variable_id),
                "status": "ok",
            }
        )
        cells[index] = assigned
        state.gridCells = cells

    def move_grid_cell(from_cell_index, to_cell_index):
        source_index = int(from_cell_index)
        target_index = int(to_cell_index)
        cells = [dict(cell) for cell in state.gridCells]
        cells[target_index] = cells[source_index]
        cells[source_index] = empty_grid_cell()
        state.gridCells = cells

    def set_grid_layout_size(rows, cols):
        rows = int(rows)
        cols = int(cols)
        cells = [dict(cell) for cell in state.gridCells]
        while len(cells) < rows * cols:
            cells.append(empty_grid_cell())
        state.gridRows = rows
        state.gridCols = cols
        state.gridCells = cells[: rows * cols]
        state.gridColumnSizes = [280 for _ in range(cols)]
        state.gridRowSizes = [352 for _ in range(rows)]
        state.gridColumnWeights = [1.0 for _ in range(cols)]
        state.gridRowWeights = [1.0 for _ in range(rows)]
        state.gridColumnTemplate = " ".join("280px" for _ in range(cols))
        state.gridRowTemplate = " ".join("352px" for _ in range(rows))
        state.gridFitColumnTemplate = " ".join(
            "minmax(180px, 1fr)" for _ in range(cols)
        )
        state.gridFitRowTemplate = " ".join("minmax(212px, 1fr)" for _ in range(rows))

    def _numeric_values(values, count, fallback):
        if isinstance(values, str):
            values = values.split(",")
        parsed = []
        for value in values or []:
            try:
                parsed.append(float(value))
            except (TypeError, ValueError):
                parsed.append(float(fallback))
        return (parsed + [float(fallback)] * count)[:count]

    def set_grid_track_sizes(axis, sizes):
        axis = str(axis)
        if axis == "column":
            state.gridColumnSizes = _numeric_values(sizes, state.gridCols, 280)
            state.gridColumnTemplate = " ".join(
                f"{round(value)}px" for value in state.gridColumnSizes
            )
        elif axis == "row":
            state.gridRowSizes = _numeric_values(sizes, state.gridRows, 352)
            state.gridRowTemplate = " ".join(
                f"{round(value)}px" for value in state.gridRowSizes
            )
        state.gridSizingMode = "static"

    def set_grid_track_weights(axis, weights):
        axis = str(axis)
        if axis == "column":
            state.gridColumnWeights = _numeric_values(weights, state.gridCols, 1)
            state.gridFitColumnTemplate = " ".join(
                f"minmax(180px, {value:g}fr)"
                for value in state.gridColumnWeights
            )
        elif axis == "row":
            state.gridRowWeights = _numeric_values(weights, state.gridRows, 1)
            state.gridFitRowTemplate = " ".join(
                f"minmax(212px, {value:g}fr)" for value in state.gridRowWeights
            )
        state.gridSizingMode = "fit"

    def show_cell_context_menu(cell_index, x, y):
        index = int(cell_index)
        cell = state.gridCells[index]
        state.contextMenuKind = "cell"
        state.contextMenuItem = str(cell.get("variable_name", "") or "")
        state.contextMenuItemLabel = state.contextMenuItem or f"Cell {index + 1}"
        state.contextMenuCellIndex = index
        state.contextMenuCellHasVariable = bool(state.contextMenuItem)
        state.contextMenuX = int(float(x))
        state.contextMenuY = int(float(y))
        state.contextMenuVisible = True

    def open_cell_context_menu(cell_index, x, y):
        show_cell_context_menu(
            cell_index,
            max(8, int(float(x)) - 216),
            max(8, int(float(y)) + 12),
        )

    def show_item_context_menu(item, x, y):
        state.contextMenuKind = "item"
        state.contextMenuItem = str(item)
        state.contextMenuItemLabel = str(item)
        state.contextMenuX = int(float(x))
        state.contextMenuY = int(float(y))
        state.contextMenuVisible = True

    def hide_context_menu_trigger():
        state.contextMenuVisible = False

    saved_grid_sizing = None

    def apply_live_grid_sizing(sizing):
        if not isinstance(sizing, dict):
            return
        mode = str(sizing.get("mode", "") or "")
        state.gridColumnSizes = _numeric_values(
            sizing.get("column_sizes"),
            state.gridCols,
            280,
        )
        state.gridRowSizes = _numeric_values(
            sizing.get("row_sizes"),
            state.gridRows,
            352,
        )
        state.gridColumnWeights = _numeric_values(
            sizing.get("column_weights"),
            state.gridCols,
            1,
        )
        state.gridRowWeights = _numeric_values(
            sizing.get("row_weights"),
            state.gridRows,
            1,
        )
        state.gridSizingMode = "fit" if mode == "fit" else "static"
        state.gridColumnTemplate = " ".join(
            f"{round(value)}px" for value in state.gridColumnSizes
        )
        state.gridRowTemplate = " ".join(
            f"{round(value)}px" for value in state.gridRowSizes
        )
        state.gridFitColumnTemplate = " ".join(
            f"minmax(180px, {value:g}fr)"
            for value in state.gridColumnWeights
        )
        state.gridFitRowTemplate = " ".join(
            f"minmax(212px, {value:g}fr)" for value in state.gridRowWeights
        )

    def save_workspace_state(live_grid_sizing=None):
        nonlocal saved_grid_sizing
        apply_live_grid_sizing(live_grid_sizing)
        saved_grid_sizing = {
            "mode": state.gridSizingMode,
            "column_sizes": list(state.gridColumnSizes),
            "row_sizes": list(state.gridRowSizes),
            "column_weights": list(state.gridColumnWeights),
            "row_weights": list(state.gridRowWeights),
        }
        if not state.workspaceStatePath:
            state.workspaceStatePath = f"/tmp/browser-{mode}.json"
        state.workspaceStateStatus = f"Saved: {state.workspaceStatePath}"

    def save_workspace_state_as(live_grid_sizing=None):
        save_workspace_state(live_grid_sizing)

    def load_workspace_state():
        if saved_grid_sizing:
            apply_live_grid_sizing(saved_grid_sizing)
        if not state.workspaceStatePath:
            state.workspaceStatePath = f"/tmp/browser-{mode}.json"
        state.workspaceStateStatus = f"Loaded: {state.workspaceStatePath}"

    server.controller.add("toggle_variable_group")(toggle_variable_group)
    server.controller.add("pick_var")(pick_var)
    server.controller.add("set_active_grid_cell")(set_active_grid_cell)
    server.controller.add("set_grid_layout_size")(set_grid_layout_size)
    server.controller.add("open_cell_context_menu")(open_cell_context_menu)
    server.controller.trigger("assign_var_to_grid_cell_trigger")(
        assign_var_to_grid_cell
    )
    server.controller.trigger("move_grid_cell_trigger")(move_grid_cell)
    server.controller.trigger("set_grid_track_sizes_trigger")(set_grid_track_sizes)
    server.controller.trigger("set_grid_track_weights_trigger")(set_grid_track_weights)
    server.controller.trigger("show_item_context_menu")(show_item_context_menu)
    server.controller.trigger("show_cell_context_menu")(show_cell_context_menu)
    server.controller.trigger("hide_context_menu_trigger")(hide_context_menu_trigger)
    server.controller.add("save_workspace_state")(save_workspace_state)
    server.controller.add("save_workspace_state_as")(save_workspace_state_as)
    server.controller.add("load_workspace_state")(load_workspace_state)
    build_ui(server, campaign_name=f"browser-{mode}.aca")
    return server


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--mode", choices=("step", "physical"), default="step")
    args = parser.parse_args()

    server = build_fixture_server(args.mode)
    server.start(
        port=args.port,
        host="127.0.0.1",
        open_browser=False,
        show_connection_info=False,
        timeout=0,
    )


if __name__ == "__main__":
    main()
