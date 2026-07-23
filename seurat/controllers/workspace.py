"""Portable JSON workspace save and load controller behavior."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Dict

from seurat.native_file_dialog import (
    choose_workspace_load_path,
    choose_workspace_save_path,
)
from seurat.models.timeline import toggle_timeline_driver
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
        ("save_workspace_state", "save_workspace_state"),
        ("save_workspace_state_as", "save_workspace_state_as"),
        ("load_workspace_state", "load_workspace_state"),
    )
    TRIGGER_BINDINGS = ()
    STATE_CHANGE_BINDINGS = ()

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
