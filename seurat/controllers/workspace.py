"""Tabbed workspace layout plus portable JSON save and load behavior."""

from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

from seurat.native_file_dialog import (
    choose_workspace_load_path,
    choose_workspace_save_path,
)
from seurat.models.timeline import toggle_timeline_driver
from seurat.models.workspace_layout import (
    active_pane_and_tab,
    add_workspace_tab as add_workspace_tab_model,
    apply_grid_snapshot,
    close_workspace_pane as close_workspace_pane_model,
    close_workspace_tab as close_workspace_tab_model,
    empty_grid_snapshot,
    grid_snapshot,
    initial_workspace_layout,
    move_workspace_tab as move_workspace_tab_model,
    normalized_tab_title,
    pane_and_tab,
    reorder_workspace_tab as reorder_workspace_tab_model,
    split_workspace as split_workspace_model,
)
from seurat.models.workspace_state import (
    WorkspaceStateError,
    default_workspace_filename,
    parse_workspace_document,
    validate_workspace_campaign,
    workspace_json,
)
from seurat.state import clear_right_panes


MAX_WORKSPACE_STATE_BYTES = 5 * 1024 * 1024


class WorkspaceControllerMixin:
    ACTION_BINDINGS = (
        ("activate_workspace_tab", "activate_workspace_tab"),
        ("add_workspace_tab", "add_workspace_tab"),
        ("rename_workspace_tab", "rename_workspace_tab"),
        ("close_workspace_tab", "close_workspace_tab"),
        ("split_workspace_pane", "split_workspace_pane"),
        ("close_workspace_pane", "close_workspace_pane"),
        ("move_workspace_tab", "move_workspace_tab"),
        ("save_workspace_state", "save_workspace_state"),
        ("save_workspace_state_as", "save_workspace_state_as"),
        ("load_workspace_state", "load_workspace_state"),
    )
    TRIGGER_BINDINGS = (
        ("reorder_workspace_tab_trigger", "reorder_workspace_tab"),
    )
    STATE_CHANGE_BINDINGS = ()

    def _workspace_layout(self) -> Dict[str, Any]:
        layout = getattr(self.state, "workspaceLayout", {})
        return deepcopy(layout) if isinstance(layout, Mapping) else {}

    def _publish_workspace_layout(self, layout: Mapping[str, Any]) -> None:
        published = deepcopy(dict(layout))
        self.state.workspaceLayout = published
        self.state.workspacePanes = deepcopy(list(published.get("panes", []) or []))
        self.state.workspaceSplitDirection = str(
            published.get("split_direction", "none") or "none"
        )
        self.state.workspaceSplitRatio = float(
            published.get("split_ratio", 0.5) or 0.5
        )
        self.state.workspaceActivePaneId = str(
            published.get("active_pane_id", "") or ""
        )
        self.state.workspaceActiveTabId = str(
            published.get("active_tab_id", "") or ""
        )

    def _stash_active_workspace_grid(self) -> Dict[str, Any]:
        layout = self._workspace_layout()
        _pane, tab = active_pane_and_tab(layout)
        if tab is not None:
            tab["grid"] = grid_snapshot(self.state)
        self._publish_workspace_layout(layout)
        return layout

    def _load_workspace_grid(self, snapshot: Mapping[str, Any]) -> None:
        needs_refresh = bool(snapshot.get("needs_refresh", False))
        apply_grid_snapshot(self.state, snapshot)
        rows, cols = self.grid_dimensions()
        self.normalize_grid_track_sizes(rows, cols)
        self.state.gridCells = self.normalize_grid_cells(
            list(getattr(self.state, "gridCells", []) or []), rows, cols
        )
        try:
            active = int(getattr(self.state, "activeGridCell", -1))
        except Exception:
            active = -1
        self.state.activeGridCell = (
            active if self.is_valid_grid_index(active) else -1
        )
        self.publish_grid_selection(
            self.normalize_grid_selection(cells=list(self.state.gridCells or []))
        )
        if needs_refresh:
            self.refresh_grid_cells()

    def _runtime_grid_from_document(
        self, saved_grid: Mapping[str, Any]
    ) -> Dict[str, Any]:
        runtime = empty_grid_snapshot(grid_snapshot(self.state))
        try:
            rows = max(
                self.GRID_MIN_ROWS,
                min(self.GRID_MAX_ROWS, int(saved_grid.get("rows", 3))),
            )
        except Exception:
            rows = 3
        try:
            cols = max(
                self.GRID_MIN_COLS,
                min(self.GRID_MAX_COLS, int(saved_grid.get("columns", 3))),
            )
        except Exception:
            cols = 3
        layout_mode = (
            "spanning"
            if str(saved_grid.get("layout_mode", "")) == "spanning"
            else "uniform"
        )
        sizing_mode = (
            "fit" if str(saved_grid.get("sizing_mode", "")) == "fit" else "static"
        )
        cell_size = int(saved_grid.get("cell_size", 300) or 300)
        fit_minimum = int(
            saved_grid.get("fit_minimum_cell_size", 180) or 180
        )
        runtime.update(
            {
                "rows": rows,
                "columns": cols,
                "layout_mode": layout_mode,
                "sizing_mode": sizing_mode,
                "cell_size": cell_size,
                "fit_minimum_cell_size": fit_minimum,
                "column_sizes": self.normalize_size_list(
                    saved_grid.get("column_sizes", []),
                    cols,
                    cell_size,
                    int(runtime.get("minimum_cell_size", 80) or 80),
                    int(runtime.get("maximum_cell_size", 5000) or 5000),
                ),
                "row_sizes": self.normalize_size_list(
                    saved_grid.get("row_sizes", []),
                    rows,
                    cell_size + self.GRID_HEADER_HEIGHT,
                    int(runtime.get("minimum_cell_size", 80) or 80)
                    + self.GRID_HEADER_HEIGHT,
                    int(runtime.get("maximum_cell_size", 5000) or 5000)
                    + self.GRID_HEADER_HEIGHT,
                ),
                "column_weights": self.normalize_weight_list(
                    saved_grid.get("column_weights", []), cols
                ),
                "row_weights": self.normalize_weight_list(
                    saved_grid.get("row_weights", []), rows
                ),
            }
        )
        runtime["column_template"] = self.grid_template_from_sizes(
            runtime["column_sizes"]
        )
        runtime["row_template"] = self.grid_template_from_sizes(
            runtime["row_sizes"]
        )
        runtime["fit_column_template"] = self.grid_fit_template_from_weights(
            runtime["column_weights"], fit_minimum
        )
        runtime["fit_row_template"] = self.grid_fit_template_from_weights(
            runtime["row_weights"], fit_minimum + self.GRID_HEADER_HEIGHT
        )
        runtime["cells"] = self.normalize_grid_cells_for_workspace(
            list(saved_grid.get("cells", []) or []), rows, cols, layout_mode
        )
        try:
            active = int(saved_grid.get("active_cell", -1))
        except Exception:
            active = -1
        runtime["active_cell"] = active if 0 <= active < rows * cols else -1
        selected = self.normalize_grid_selection(
            list(saved_grid.get("selected_cells", []) or []), runtime["cells"]
        )
        runtime["selected_cells"] = selected
        runtime["selected_cell_map"] = {
            str(index): True for index in selected
        }
        try:
            driver = int(saved_grid.get("timeline_driver_cell", -1))
        except Exception:
            driver = -1
        runtime["timeline_driver_cell"] = (
            driver if 0 <= driver < rows * cols else -1
        )
        runtime["needs_refresh"] = True
        return runtime

    def normalize_grid_cells_for_workspace(
        self, cells, rows: int, cols: int, layout_mode: str
    ):
        previous_mode = getattr(self.state, "gridLayoutMode", "uniform")
        try:
            self.state.gridLayoutMode = layout_mode
            return self.normalize_grid_cells(cells, rows, cols)
        finally:
            self.state.gridLayoutMode = previous_mode

    def _restore_workspace_layout(self, saved_workspace: Any) -> None:
        if not isinstance(saved_workspace, Mapping):
            self._publish_workspace_layout(
                initial_workspace_layout(grid_snapshot(self.state))
            )
            return

        active_pane_id = str(saved_workspace.get("active_pane_id", "") or "")
        active_tab_id = str(saved_workspace.get("active_tab_id", "") or "")
        panes = []
        for saved_pane in list(saved_workspace.get("panes", []) or []):
            tabs = []
            for saved_tab in list(saved_pane.get("tabs", []) or []):
                tab_id = str(saved_tab.get("id", "") or "")
                grid = (
                    grid_snapshot(self.state)
                    if tab_id == active_tab_id
                    else self._runtime_grid_from_document(
                        saved_tab.get("grid", {})
                    )
                )
                tabs.append(
                    {
                        "id": tab_id,
                        "title": normalized_tab_title(
                            saved_tab.get("title", ""), "View"
                        ),
                        "grid": grid,
                    }
                )
            panes.append(
                {
                    "id": str(saved_pane.get("id", "") or ""),
                    "active_tab_id": str(
                        saved_pane.get("active_tab_id", "") or ""
                    ),
                    "tabs": tabs,
                }
            )
        layout = {
            "split_direction": str(
                saved_workspace.get("split_direction", "none") or "none"
            ),
            "split_ratio": float(
                saved_workspace.get("split_ratio", 0.5) or 0.5
            ),
            "active_pane_id": active_pane_id,
            "active_tab_id": active_tab_id,
            "panes": panes,
        }
        self._publish_workspace_layout(layout)

    def _activate_workspace_target(
        self, pane_id: str, tab_id: str, *, stash: bool = True
    ) -> bool:
        layout = (
            self._stash_active_workspace_grid()
            if stash
            else self._workspace_layout()
        )
        pane, tab = pane_and_tab(layout, pane_id, tab_id)
        if pane is None or tab is None:
            return False
        pane["active_tab_id"] = tab["id"]
        layout["active_pane_id"] = pane["id"]
        layout["active_tab_id"] = tab["id"]
        self._publish_workspace_layout(layout)
        self._load_workspace_grid(tab.get("grid", {}))
        return True

    def activate_workspace_tab(self, pane_id: str, tab_id: str, **_):
        self._activate_workspace_target(str(pane_id or ""), str(tab_id or ""))

    def add_workspace_tab(self, pane_id: str = "", **_):
        layout = self._stash_active_workspace_grid()
        target_pane = str(pane_id or layout.get("active_pane_id", ""))
        layout, tab_id = add_workspace_tab_model(
            layout, target_pane, grid_snapshot(self.state)
        )
        self._publish_workspace_layout(layout)
        self._activate_workspace_target(
            str(layout.get("active_pane_id", "")), tab_id, stash=False
        )

    def rename_workspace_tab(
        self, pane_id: str, tab_id: str, title: str, **_
    ):
        layout = self._stash_active_workspace_grid()
        _pane, tab = pane_and_tab(layout, pane_id, tab_id)
        if tab is None or title is None:
            return
        tab["title"] = normalized_tab_title(title, str(tab.get("title", "View")))
        self._publish_workspace_layout(layout)

    def close_workspace_tab(
        self, pane_id: str, tab_id: str, confirmed: bool = True, **_
    ):
        if not confirmed:
            return
        layout = self._stash_active_workspace_grid()
        layout = close_workspace_tab_model(layout, pane_id, tab_id)
        self._publish_workspace_layout(layout)
        self._activate_workspace_target(
            str(layout.get("active_pane_id", "")),
            str(layout.get("active_tab_id", "")),
            stash=False,
        )

    def split_workspace_pane(self, direction: str = "horizontal", **_):
        layout = self._stash_active_workspace_grid()
        layout, _pane_id = split_workspace_model(
            layout, direction, grid_snapshot(self.state)
        )
        self._publish_workspace_layout(layout)
        self._activate_workspace_target(
            str(layout.get("active_pane_id", "")),
            str(layout.get("active_tab_id", "")),
            stash=False,
        )

    def close_workspace_pane(
        self, pane_id: str, confirmed: bool = True, **_
    ):
        if not confirmed:
            return
        layout = self._stash_active_workspace_grid()
        layout = close_workspace_pane_model(layout, pane_id)
        self._publish_workspace_layout(layout)
        self._activate_workspace_target(
            str(layout.get("active_pane_id", "")),
            str(layout.get("active_tab_id", "")),
            stash=False,
        )

    def move_workspace_tab(self, pane_id: str, tab_id: str, **_):
        layout = self._stash_active_workspace_grid()
        layout = move_workspace_tab_model(layout, pane_id, tab_id)
        self._publish_workspace_layout(layout)
        self._activate_workspace_target(
            str(layout.get("active_pane_id", "")),
            str(layout.get("active_tab_id", "")),
            stash=False,
        )

    def reorder_workspace_tab(
        self, pane_id: str, tab_id: str, insertion_index: int, **_
    ):
        layout = self._stash_active_workspace_grid()
        layout = reorder_workspace_tab_model(
            layout, pane_id, tab_id, insertion_index
        )
        self._publish_workspace_layout(layout)

    def _set_workspace_error(self, message: str) -> None:
        self.state.workspaceStateStatus = ""
        self.state.workspaceStateError = str(message or "")

    def _apply_live_grid_sizing(self, sizing: Any) -> None:
        if not isinstance(sizing, Mapping):
            return

        mode = str(sizing.get("mode", "") or "").strip().lower()
        if mode in {"fit", "static"}:
            self.state.gridSizingMode = mode

        self.normalize_grid_sizing()
        rows, cols = self.grid_dimensions()
        column_sizes = sizing.get("column_sizes")
        row_sizes = sizing.get("row_sizes")
        column_weights = sizing.get("column_weights")
        row_weights = sizing.get("row_weights")

        if column_sizes not in (None, ""):
            self.state.gridColumnSizes = self.normalize_size_list(
                column_sizes,
                cols,
                int(self.state.gridCellSize),
                int(self.state.gridMinCellSize),
                int(self.state.gridMaxCellSize),
            )
        if row_sizes not in (None, ""):
            self.state.gridRowSizes = self.normalize_size_list(
                row_sizes,
                rows,
                int(self.state.gridCellSize) + self.GRID_HEADER_HEIGHT,
                int(self.state.gridMinCellSize) + self.GRID_HEADER_HEIGHT,
                int(self.state.gridMaxCellSize) + self.GRID_HEADER_HEIGHT,
            )
        if column_weights not in (None, ""):
            self.state.gridColumnWeights = self.normalize_weight_list(
                column_weights,
                cols,
            )
        if row_weights not in (None, ""):
            self.state.gridRowWeights = self.normalize_weight_list(
                row_weights,
                rows,
            )

        self.normalize_grid_track_sizes(rows, cols)

    def _restore_grid_sizing(
        self,
        grid: Mapping[str, Any],
        rows: int,
        cols: int,
    ) -> None:
        self.state.gridSizingMode = str(
            grid.get("sizing_mode", "static") or "static"
        )
        self.state.gridCellSize = grid.get("cell_size", 300)
        self.state.gridFitMinCellSize = grid.get(
            "fit_minimum_cell_size", 180
        )
        self.state.gridColumnSizes = list(grid.get("column_sizes", []) or [])
        self.state.gridRowSizes = list(grid.get("row_sizes", []) or [])
        self.state.gridColumnWeights = list(
            grid.get("column_weights", []) or []
        )
        self.state.gridRowWeights = list(grid.get("row_weights", []) or [])
        self.normalize_grid_track_sizes(rows, cols)

    def _save_workspace_to_path(self, path: str) -> bool:
        self._stash_active_workspace_grid()
        target = Path(path).expanduser().resolve()
        if target.suffix.lower() != ".json":
            target = Path(f"{target}.json")
        try:
            target.write_text(
                workspace_json(self.state, self.campaign_path),
                encoding="utf-8",
            )
        except Exception as e:
            self._set_workspace_error(
                f"Could not save state: {type(e).__name__}: {e}"
            )
            return False

        self.state.workspaceStatePath = str(target)
        self.state.workspaceStateStatus = f"Saved: {target}"
        self.state.workspaceStateError = ""
        return True

    def save_workspace_state(self, live_grid_sizing=None, **_):
        current_path = str(self.state.workspaceStatePath or "")
        if not current_path:
            return self.save_workspace_state_as(live_grid_sizing)
        self._apply_live_grid_sizing(live_grid_sizing)
        self._save_workspace_to_path(current_path)

    def save_workspace_state_as(self, live_grid_sizing=None, **_):
        self._apply_live_grid_sizing(live_grid_sizing)
        try:
            path = choose_workspace_save_path(
                default_workspace_filename(self.campaign_path),
                current_path=str(self.state.workspaceStatePath or ""),
                campaign_path=self.campaign_path,
            )
        except Exception as e:
            self._set_workspace_error(
                f"Could not open Save As dialog: {type(e).__name__}: {e}"
            )
            return
        if path:
            self._save_workspace_to_path(path)

    def load_workspace_state(self, **_):
        try:
            path = choose_workspace_load_path(
                current_path=str(self.state.workspaceStatePath or ""),
                campaign_path=self.campaign_path,
            )
        except Exception as e:
            self._set_workspace_error(
                f"Could not open Load dialog: {type(e).__name__}: {e}"
            )
            return
        if not path:
            return

        source = Path(path).expanduser().resolve()
        try:
            if source.suffix.lower() != ".json":
                raise WorkspaceStateError("State file must have a .json extension")
            if source.stat().st_size > MAX_WORKSPACE_STATE_BYTES:
                raise WorkspaceStateError("State file exceeds the 5 MiB limit")
            document = parse_workspace_document(source.read_bytes())
            self.restore_workspace_state(document)
        except (WorkspaceStateError, TypeError, ValueError) as e:
            self._set_workspace_error(str(e))
            return
        except Exception as e:
            self._set_workspace_error(
                f"Could not load state: {type(e).__name__}: {e}"
            )
            return

        self.state.workspaceStatePath = str(source)
        self.state.workspaceStateStatus = f"Loaded: {source}"
        self.state.workspaceStateError = ""

    def restore_workspace_state(self, document: Dict[str, Any]) -> None:
        validate_workspace_campaign(document, self.campaign_path)
        saved_state = document["state"]
        catalog = saved_state["catalog"]
        grid = saved_state["grid"]
        visualization = saved_state["visualization"]

        self.state.variablePaneView = (
            "files"
            if str(catalog.get("variable_pane_view", "")) == "files"
            else "variables"
        )
        collapsed_by_view = catalog.get(
            "variable_group_collapsed_by_view",
            {"variables": {}, "files": {}},
        )
        self.state.variableGroupCollapsedByView = (
            dict(collapsed_by_view)
            if isinstance(collapsed_by_view, dict)
            else {"variables": {}, "files": {}}
        )
        self.state.showOnlyVisualizedVars = bool(
            catalog.get("show_only_visualized_variables", False)
        )
        self.state.queryText = str(catalog.get("query_text", "") or "")
        if not self.update_query_state():
            raise WorkspaceStateError(
                f"Saved query is not valid: {self.state.queryError}"
            )
        self.refresh_variable_list()
        viewer_action = catalog.get("viewer_action", {})
        self.state.activeViewerActionPlan = (
            dict(viewer_action) if isinstance(viewer_action, dict) else {}
        )
        self.state.activeNaturalLanguageQuery = str(
            catalog.get("natural_language_query", "") or ""
        )
        if self.state.activeNaturalLanguageQuery:
            self.state.queryViewLabel = self.state.activeNaturalLanguageQuery

        self.state.scalarPlotPolicy = str(
            visualization.get("scalar_plot_policy", "always") or "always"
        )
        self.normalize_scalar_plot_policy()

        self.state.gridRows = grid.get("rows", 3)
        self.state.gridCols = grid.get("columns", 3)
        self.state.gridLayoutMode = str(
            grid.get("layout_mode", "uniform") or "uniform"
        )

        rows, cols = self.grid_dimensions()
        self._restore_grid_sizing(grid, rows, cols)
        self.state.gridCells = self.normalize_grid_cells(
            list(grid.get("cells", []) or []),
            rows,
            cols,
        )
        self.refresh_grid_cells()
        self._restore_grid_sizing(grid, rows, cols)

        try:
            active = int(grid.get("active_cell", -1))
        except Exception:
            active = -1
        self.state.activeGridCell = (
            active if self.is_valid_grid_index(active) else -1
        )
        selected = self.normalize_grid_selection(
            list(grid.get("selected_cells", []) or []),
            list(self.state.gridCells or []),
        )
        self.publish_grid_selection(selected)

        try:
            driver = int(grid.get("timeline_driver_cell", -1))
        except Exception:
            driver = -1
        self.state.timelineDriverCell = toggle_timeline_driver(
            list(self.state.gridCells or []),
            -1,
            driver,
        )

        selected_variable = str(
            catalog.get("selected_variable", "") or ""
        )
        if selected_variable not in list(self.state.variableNames or []):
            selected_variable = ""
        self.state.selectedVar = selected_variable
        self.state.draggedVar = ""
        if selected_variable:
            self.update_selected_var_panels(selected_variable)
        else:
            clear_right_panes(self.state)
        self.clear_context_menu_state()
        self._restore_workspace_layout(saved_state.get("workspace"))
