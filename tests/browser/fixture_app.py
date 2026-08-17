"""Deterministic Trame application used by the browser tests."""

import argparse
import sys
from copy import deepcopy
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from seurat import module as seurat_module  # noqa: E402
from seurat.controllers.catalog import _filter_variable_groups  # noqa: E402
from seurat.models.grid import empty_grid_cell  # noqa: E402
from seurat.models.workspace_layout import (  # noqa: E402
    active_pane_and_tab,
    add_workspace_tab as add_workspace_tab_model,
    apply_grid_snapshot,
    close_workspace_pane as close_workspace_pane_model,
    close_workspace_tab as close_workspace_tab_model,
    grid_snapshot,
    initial_workspace_layout,
    move_workspace_tab as move_workspace_tab_model,
    normalized_tab_title,
    pane_and_tab,
    reorder_workspace_tab as reorder_workspace_tab_model,
    split_workspace as split_workspace_model,
)
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


def _scalar_field_cell(background):
    is_white = background == "white"
    background_color = "#ffffff" if is_white else "#000000"
    foreground_color = "#111111" if is_white else "#ffffff"
    cell = empty_grid_cell()
    cell.update(
        {
            "variable_id": f"field_{background}",
            "variable_name": f"field_{background}",
            "display_title": f"field_{background}",
            "variable_type": "scalarField",
            "payload_type": "SCALAR_FIELD",
            "visualization_item_type": "SCALAR_FIELD",
            "media_type": "image",
            "status": "ok",
            "src": _image_source(background_color),
            "scalar_field_settings": {
                "background": background,
                "background_color": background_color,
                "foreground_color": foreground_color,
                "show_axes": True,
                "show_colorbar": True,
                "colorbar_gradient": "linear-gradient(to top, #440154, #fde725)",
            },
            "scalar_field_axes": {
                "x": {
                    "label": "R",
                    "start": 0.2,
                    "end": 4.6,
                    "ticks": [
                        {"position": 0, "value": 0.2, "label": "0.2"},
                        {"position": 50, "value": 2.4, "label": "2.4"},
                        {"position": 100, "value": 4.6, "label": "4.6"},
                    ],
                },
                "y": {
                    "label": "Z",
                    "start": -2.5,
                    "end": 2.5,
                    "ticks": [
                        {"position": 0, "value": -2.5, "label": "-2.5"},
                        {"position": 50, "value": 0.0, "label": "0"},
                        {"position": 100, "value": 2.5, "label": "2.5"},
                    ],
                },
            },
            "scalar_field_colorbar_min": "-1",
            "scalar_field_colorbar_max": "1",
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
    state.filteredVariableGroups = []
    state.variableNames = ["internal_energy", "current_z"]
    state.variableLabelsById = {
        "internal_energy": "internal_energy",
        "current_z": "current_z",
    }
    state.detailsSelectedVar = "internal_energy"
    state.detailsSelectedVarId = "internal_energy"
    state.detailsNumSources = 2
    state.sourceRowsAll = [
        {
            "_key": "source-128",
            "variable_id": "internal_energy",
            "source_dataset": "run-128/output.bp",
            "sourceName": "run-128/output.bp",
            "min": "1",
            "max": "9",
            "min_value": 1.0,
            "max_value": 9.0,
        },
        {
            "_key": "source-64",
            "variable_id": "internal_energy",
            "source_dataset": "run-64/output.bp",
            "sourceName": "run-64/output.bp",
            "min": "2",
            "max": "4",
            "min_value": 2.0,
            "max_value": 4.0,
        },
    ]
    state.sourceRows = list(state.sourceRowsAll)
    state.selectedSourceKeys = ["source-128"]
    state.selectedSourceLabel = "run-128/output.bp"
    state.queryAssistantAvailable = True
    state.queryAssistantProvider = "Deterministic browser fixture"
    state.variableGroupCollapsed = {"0D": False, "2D": False}
    state.variableGroupCollapsedByView = {
        "variables": dict(state.variableGroupCollapsed),
        "files": {},
    }
    state.gridRows = 1
    state.gridCols = 3
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
    if mode in {"scalar", "scalar-settings"}:
        state.gridCells = [
            _scalar_field_cell("black"),
            _scalar_field_cell("white"),
            empty_grid_cell(),
        ]
    else:
        state.gridCells = [
            _plot_cell(mode),
            _image_sequence_cell(mode),
            empty_grid_cell(),
        ]
    state.workspaceLayout = initial_workspace_layout(grid_snapshot(state))
    state.workspacePanes = deepcopy(state.workspaceLayout["panes"])

    if mode == "scalar-settings":
        state.showScalarFieldSettingsModal = True
        state.scalarFieldSettingsCellIndex = 0
        state.scalarFieldSettingsTitle = "field_black"
        state.scalarFieldSettingsShowHeatmap = True
        state.scalarFieldSettingsShowContours = False
        state.scalarFieldSettingsColormap = "viridis"
        state.scalarFieldSettingsBackground = "black"
        state.scalarFieldSettingsRangeAuto = True
        state.scalarFieldSettingsShowColorbar = True
        state.scalarFieldSettingsShowAxes = True
        state.scalarFieldSettingsContourLevelMode = "range"
        state.scalarFieldSettingsContourValues = "-1, 0, 1"
        state.scalarFieldSettingsContourMin = "-1"
        state.scalarFieldSettingsContourMax = "1"
        state.scalarFieldSettingsContourCount = 5
        state.scalarFieldSettingsContourColor = "#ffffff"

    def toggle_variable_group(group_name):
        collapsed = dict(state.variableGroupCollapsed or {})
        collapsed[str(group_name)] = not bool(collapsed.get(str(group_name), False))
        state.variableGroupCollapsed = collapsed

    def publish_workspace_layout(layout):
        state.workspaceLayout = deepcopy(layout)
        state.workspacePanes = deepcopy(layout["panes"])
        state.workspaceSplitDirection = layout["split_direction"]
        state.workspaceSplitRatio = layout["split_ratio"]
        state.workspaceActivePaneId = layout["active_pane_id"]
        state.workspaceActiveTabId = layout["active_tab_id"]

    def stash_active_workspace_grid():
        layout = deepcopy(state.workspaceLayout)
        _pane, tab = active_pane_and_tab(layout)
        if tab is not None:
            tab["grid"] = grid_snapshot(state)
        publish_workspace_layout(layout)
        return layout

    def activate_workspace_tab(pane_id, tab_id):
        layout = stash_active_workspace_grid()
        pane, tab = pane_and_tab(layout, pane_id, tab_id)
        if pane is None or tab is None:
            return
        pane["active_tab_id"] = tab["id"]
        layout["active_pane_id"] = pane["id"]
        layout["active_tab_id"] = tab["id"]
        publish_workspace_layout(layout)
        apply_grid_snapshot(state, tab["grid"])

    def add_workspace_tab(pane_id=""):
        layout = stash_active_workspace_grid()
        layout, tab_id = add_workspace_tab_model(
            layout,
            pane_id or layout["active_pane_id"],
            grid_snapshot(state),
        )
        publish_workspace_layout(layout)
        pane, tab = pane_and_tab(layout, layout["active_pane_id"], tab_id)
        if pane is not None and tab is not None:
            apply_grid_snapshot(state, tab["grid"])

    def rename_workspace_tab(pane_id, tab_id, title):
        if title is None:
            return
        layout = stash_active_workspace_grid()
        _pane, tab = pane_and_tab(layout, pane_id, tab_id)
        if tab is not None:
            tab["title"] = normalized_tab_title(title, tab["title"])
        publish_workspace_layout(layout)

    def load_active_workspace_grid(layout):
        publish_workspace_layout(layout)
        _pane, tab = active_pane_and_tab(layout)
        if tab is not None:
            apply_grid_snapshot(state, tab["grid"])

    def close_workspace_tab(pane_id, tab_id, confirmed=True):
        if confirmed:
            load_active_workspace_grid(
                close_workspace_tab_model(
                    stash_active_workspace_grid(), pane_id, tab_id
                )
            )

    def split_workspace_pane(direction="horizontal"):
        layout, _pane_id = split_workspace_model(
            stash_active_workspace_grid(), direction, grid_snapshot(state)
        )
        load_active_workspace_grid(layout)

    def close_workspace_pane(pane_id, confirmed=True):
        if confirmed:
            load_active_workspace_grid(
                close_workspace_pane_model(stash_active_workspace_grid(), pane_id)
            )

    def move_workspace_tab(pane_id, tab_id):
        load_active_workspace_grid(
            move_workspace_tab_model(
                stash_active_workspace_grid(), pane_id, tab_id
            )
        )

    def reorder_workspace_tab(pane_id, tab_id, insertion_index):
        layout = reorder_workspace_tab_model(
            stash_active_workspace_grid(), pane_id, tab_id, insertion_index
        )
        publish_workspace_layout(layout)

    @state.change("variableSearchText")
    def filter_variable_groups(variableSearchText, **_):
        search_text = str(variableSearchText or "").strip()
        state.filteredVariableGroups = (
            _filter_variable_groups(state.variableGroups, search_text)
            if search_text
            else []
        )

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

    def show_item_context_menu(item, x, y):
        state.contextMenuKind = "item"
        state.contextMenuItem = str(item)
        state.contextMenuItemLabel = str(item)
        state.contextMenuX = int(float(x))
        state.contextMenuY = int(float(y))
        state.contextMenuVisible = True

    def hide_context_menu_trigger():
        state.contextMenuVisible = False

    def show_tab_context_menu(pane_id, tab_id, x, y):
        _pane, tab = pane_and_tab(state.workspaceLayout, pane_id, tab_id)
        if tab is None:
            return
        state.contextMenuKind = "tab"
        state.contextMenuItemLabel = tab["title"]
        state.contextMenuTabPaneId = pane_id
        state.contextMenuTabId = tab_id
        state.contextMenuTabCanClose = sum(
            len(pane["tabs"]) for pane in state.workspaceLayout["panes"]
        ) > 1
        state.contextMenuX = int(float(x))
        state.contextMenuY = int(float(y))
        state.contextMenuVisible = True

    def context_menu_tab_rename(title):
        rename_workspace_tab(
            state.contextMenuTabPaneId,
            state.contextMenuTabId,
            title,
        )
        state.contextMenuVisible = False

    def context_menu_tab_close(confirmed=True):
        if confirmed and state.contextMenuTabCanClose:
            close_workspace_tab(
                state.contextMenuTabPaneId,
                state.contextMenuTabId,
            )
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

    def toggle_scalar_field_background():
        state.scalarFieldSettingsBackground = (
            "black"
            if state.scalarFieldSettingsBackground == "white"
            else "white"
        )

    def update_scalar_field_contour_color(color):
        state.scalarFieldSettingsContourColor = str(color or "#ffffff")

    def reset_query_assistant_proposal():
        state.queryAssistantProposalText = ""
        state.queryAssistantProposalSummary = ""
        state.queryAssistantActionPlan = {}
        state.queryAssistantExplanation = ""
        state.queryAssistantStatus = ""
        state.queryAssistantError = ""
        state.queryAssistantTargetCellIndex = -1
        state.queryAssistantVisualizationName = ""

    def open_query_assistant():
        previous_target = state.queryAssistantTarget
        reset_query_assistant_proposal()
        state.queryAssistantTarget = "catalog"
        if previous_target != "catalog":
            state.queryAssistantRequestText = ""
        state.showQueryAssistant = True

    def open_source_query_assistant():
        reset_query_assistant_proposal()
        state.queryAssistantTarget = "source_filter"
        state.queryAssistantRequestText = state.sourceFilterDraftText
        state.showQueryAssistant = True

    def open_visualization_assistant():
        previous_target = state.queryAssistantTarget
        reset_query_assistant_proposal()
        state.queryAssistantTarget = "visualization"
        if previous_target != "visualization":
            state.queryAssistantRequestText = ""
        state.showQueryAssistant = True

    def close_query_assistant():
        state.showQueryAssistant = False

    def translate_query_request():
        if state.queryAssistantTarget == "source_filter":
            state.queryAssistantProposalText = (
                'max > 5.0 and contains(source_dataset, "128")'
            )
            state.queryAssistantProposalSummary = (
                "Select sources for internal_energy with 2 conditions."
            )
            state.queryAssistantStatus = "Valid · 1 source row"
            state.queryAssistantVariableCount = 1
            state.queryAssistantSourceCount = 1
        elif state.queryAssistantTarget == "visualization":
            variable_id = (
                "current_z"
                if "current" in state.queryAssistantRequestText.lower()
                else "internal_energy"
            )
            state.queryAssistantProposalText = ""
            state.queryAssistantVisualizationName = "viewer default"
            state.queryAssistantTargetCellIndex = state.activeGridCell
            state.queryAssistantProposalSummary = (
                f"Add {variable_id} to grid cell {state.activeGridCell + 1} "
                "using viewer default."
            )
            state.queryAssistantStatus = (
                f"Valid · {variable_id} · grid cell {state.activeGridCell + 1}"
            )
            state.queryAssistantVariableCount = 1
            state.queryAssistantSourceCount = 0
        else:
            state.queryAssistantProposalText = "var == 'internal_energy'"
            state.queryAssistantProposalSummary = (
                "Select variables for internal_energy."
            )
            state.queryAssistantStatus = "Valid · 1 variable"
            state.queryAssistantVariableCount = 1
            state.queryAssistantSourceCount = 0
        if state.queryAssistantTarget == "visualization":
            state.queryAssistantActionPlan = {
                "version": 1,
                "actions": [
                    {
                        "type": "visualization.add",
                        "arguments": {
                            "variable_id": variable_id,
                            "target": "active_cell",
                        },
                    }
                ],
            }
        else:
            state.queryAssistantActionPlan = {
                "version": 1,
                "actions": [
                    {
                        "type": "catalog.query",
                        "arguments": {
                            "select": "variables",
                            "result_variable_id": "internal_energy",
                        },
                    }
                ],
            }
        state.queryAssistantExplanation = (
            f"Add {variable_id} to the active grid cell."
            if state.queryAssistantTarget == "visualization"
            else "Select the exact internal_energy variable."
        )

    def validate_query_proposal():
        if state.queryAssistantTarget == "source_filter":
            state.queryAssistantStatus = "Valid · 1 source row"
        elif state.queryAssistantTarget == "catalog":
            state.queryAssistantStatus = "Valid · 1 variable"

    def apply_query_proposal():
        if state.queryAssistantTarget == "source_filter":
            state.sourceFilterDraftText = state.queryAssistantProposalText
            state.sourceFilterText = state.queryAssistantProposalText
            state.sourceRows = [dict(state.sourceRowsAll[0])]
        elif state.queryAssistantTarget == "visualization":
            action = state.queryAssistantActionPlan["actions"][0]
            assign_var_to_grid_cell(
                action["arguments"]["variable_id"],
                state.queryAssistantTargetCellIndex,
            )
        else:
            state.queryText = state.queryAssistantProposalText
        state.showQueryAssistant = False

    def toggle_sources():
        state.sourceDialogTitle = "Sources: internal_energy"
        state.showSourcesModal = not bool(state.showSourcesModal)

    server.controller.add("toggle_variable_group")(toggle_variable_group)
    server.controller.add("activate_workspace_tab")(activate_workspace_tab)
    server.controller.add("add_workspace_tab")(add_workspace_tab)
    server.controller.add("rename_workspace_tab")(rename_workspace_tab)
    server.controller.add("close_workspace_tab")(close_workspace_tab)
    server.controller.add("context_menu_tab_rename")(context_menu_tab_rename)
    server.controller.add("context_menu_tab_close")(context_menu_tab_close)
    server.controller.add("split_workspace_pane")(split_workspace_pane)
    server.controller.add("close_workspace_pane")(close_workspace_pane)
    server.controller.add("move_workspace_tab")(move_workspace_tab)
    server.controller.add("set_active_grid_cell")(set_active_grid_cell)
    server.controller.add("set_grid_layout_size")(set_grid_layout_size)
    server.controller.trigger("assign_var_to_grid_cell_trigger")(
        assign_var_to_grid_cell
    )
    server.controller.trigger("move_grid_cell_trigger")(move_grid_cell)
    server.controller.trigger("reorder_workspace_tab_trigger")(
        reorder_workspace_tab
    )
    server.controller.trigger("set_grid_track_sizes_trigger")(set_grid_track_sizes)
    server.controller.trigger("set_grid_track_weights_trigger")(set_grid_track_weights)
    server.controller.trigger("show_item_context_menu")(show_item_context_menu)
    server.controller.trigger("show_cell_context_menu")(show_cell_context_menu)
    server.controller.trigger("show_tab_context_menu")(show_tab_context_menu)
    server.controller.trigger("hide_context_menu_trigger")(hide_context_menu_trigger)
    server.controller.add("save_workspace_state")(save_workspace_state)
    server.controller.add("save_workspace_state_as")(save_workspace_state_as)
    server.controller.add("load_workspace_state")(load_workspace_state)
    server.controller.add("toggle_scalar_field_background")(
        toggle_scalar_field_background
    )
    server.controller.add("update_scalar_field_contour_color")(
        update_scalar_field_contour_color
    )
    server.controller.add("toggle_sources")(toggle_sources)
    server.controller.add("open_query_assistant")(open_query_assistant)
    server.controller.add("open_source_query_assistant")(
        open_source_query_assistant
    )
    server.controller.add("open_visualization_assistant")(
        open_visualization_assistant
    )
    server.controller.add("close_query_assistant")(close_query_assistant)
    server.controller.add("translate_query_request")(translate_query_request)
    server.controller.add("validate_query_proposal")(validate_query_proposal)
    server.controller.add("apply_query_proposal")(apply_query_proposal)
    build_ui(server, campaign_name=f"browser-{mode}.aca")
    return server


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument(
        "--mode",
        choices=("step", "physical", "scalar", "scalar-settings"),
        default="step",
    )
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
