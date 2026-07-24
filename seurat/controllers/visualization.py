"""Visualization, plot, scalar-field, and plugin controller behavior."""

from typing import Any, Dict, List, Optional

from config import MAX_MOVIE_FRAMES, MOVIE_FPS
from db import (
    GENERATED_SCALAR_PLOT_VIS,
    SCALAR_FIELD_COLORMAP_CSS_GRADIENTS,
    SCALAR_FIELD_COLORMAPS,
    SCALAR_FIELD_VARIABLE_TYPE,
)
from plugin_runtime import (
    build_plugin_meta,
    is_plugin_visualization,
    plugin_id_from_visualization,
    plugin_scope,
    plugin_options_schema,
    render_plugin_tile,
    render_source_plugin_tile,
    supported_source_plugins,
    supported_plugin_visualizations,
    normalize_plugin_options,
)
from query_parser import and_filter
from seurat.models import plot as plot_model
from seurat.models.plugin_options import plugin_option_rows, plugin_options_from_rows
from seurat.models.grid import (
    assign_cell,
    empty_grid_cell,
    empty_grid_cell_like,
    preserve_grid_geometry,
)
from seurat.models.source_selection import (
    source_fields_from_row,
    source_filter_from_row,
)
from state_init import fmt


class VisualizationControllerMixin:
    ACTION_BINDINGS = (
        ("cancel_scalar_plot_generation", "cancel_scalar_plot_generation"),
        ("confirm_scalar_plot_generation", "confirm_scalar_plot_generation"),
        ("cancel_plot_settings", "cancel_plot_settings"),
        ("open_plot_settings_plugin_options", "open_plot_settings_plugin_options"),
        ("cancel_plugin_options", "cancel_plugin_options"),
        ("reset_plugin_options", "reset_plugin_options"),
        ("update_plugin_option_value", "update_plugin_option_value"),
        ("apply_plugin_options", "apply_plugin_options"),
        ("cancel_scalar_field_settings", "cancel_scalar_field_settings"),
        ("reset_scalar_field_settings", "reset_scalar_field_settings"),
        ("apply_scalar_field_settings", "apply_scalar_field_settings"),
        ("reset_plot_settings", "reset_plot_settings"),
        ("update_plot_background_color", "update_plot_background_color"),
        ("update_plot_grid_color", "update_plot_grid_color"),
        ("update_plot_cursor_color", "update_plot_cursor_color"),
        ("update_plot_series_color", "update_plot_series_color"),
        ("update_plot_series_line_style", "update_plot_series_line_style"),
        ("apply_plot_settings", "apply_plot_settings"),
    )
    TRIGGER_BINDINGS = ()
    STATE_CHANGE_BINDINGS = ()

    assign_plot_series_keys = staticmethod(plot_model.assign_plot_series_keys)
    axis_has_positive_data = staticmethod(plot_model.axis_has_positive_data)
    clean_line_style = staticmethod(plot_model.clean_line_style)
    clean_plot_color = staticmethod(plot_model.clean_plot_color)
    existing_plot_settings = staticmethod(plot_model.existing_plot_settings)
    finite_float = staticmethod(plot_model.finite_float)
    normalize_plot_settings = staticmethod(plot_model.normalize_plot_settings)
    plot_series = staticmethod(plot_model.plot_series)
    plot_series_rows_for_tile = staticmethod(plot_model.plot_series_rows_for_tile)
    plugin_option_rows = staticmethod(plugin_option_rows)
    plugin_options_from_rows = staticmethod(plugin_options_from_rows)
    settings_value_text = staticmethod(plot_model.settings_value_text)
    to_bool = staticmethod(plot_model.to_bool)
    valid_title_extrema = staticmethod(plot_model.valid_extrema)

    def merge_visualization_names(
        self, base_names: List[str], plugin_names: List[str]
    ) -> List[str]:
        out: List[str] = []
        for raw_name in list(base_names or []) + list(plugin_names or []):
            name = str(raw_name or "").strip()
            if name and name not in out:
                out.append(name)
        return out

    def plugin_candidate(
        self,
        variable_id: str,
        source_filter: Optional[Dict[str, Any]] = None,
        extra_filter: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        try:
            candidate = self.db.scalar_plot_candidate(
                variable_id,
                source_filter=source_filter or None,
                extra_filter=extra_filter,
            )
            if candidate:
                candidate["source_variables"] = self.plugin_source_variables(candidate)
            return candidate
        except Exception:
            return {}

    def source_plugin_context_for_cell(self, cell: Dict[str, Any]) -> Dict[str, Any]:
        source_fields_items = self.source_fields_list_from_cell(cell)
        source_fields = dict(source_fields_items[0] if source_fields_items else {})
        if not source_fields:
            source_fields = {
                "_source_key": str(cell.get("_source_key", "") or ""),
                "source_dataset": str(cell.get("source_dataset", "") or ""),
                "schema_file_group": str(cell.get("schema_file_group", "") or ""),
                "schema_mode": str(cell.get("schema_mode", "") or ""),
                "producer": str(cell.get("producer", "") or ""),
                "casename": str(cell.get("casename", "") or ""),
                "file": str(cell.get("file", "") or ""),
            }

        source_variables = (
            self.plugin_source_variables({"source_fields": source_fields})
            if source_fields
            else []
        )
        metadata = cell.get("metadata", {}) or {}
        if not isinstance(metadata, dict):
            metadata = {}
        return {
            "variable_id": str(cell.get("variable_id", "") or ""),
            "variable_name": str(
                cell.get("variable_name", "") or cell.get("variable_id", "") or ""
            ),
            "variable_path": str(cell.get("variable_path", "") or ""),
            "source_dataset": str(
                source_fields.get("source_dataset", "")
                or cell.get("source_dataset", "")
                or ""
            ),
            "source_fields": source_fields,
            "source_variables": source_variables,
            "metadata": dict(metadata),
            "ndims": None,
            "steps_count": 1,
            "shape": [],
            "min": cell.get("min", None),
            "max": cell.get("max", None),
        }

    def source_plugin_menu_entries_for_cell(
        self, cell: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        try:
            meta = self.source_plugin_context_for_cell(cell)
            plugins = supported_source_plugins(meta)
        except Exception:
            plugins = []
        return [
            {
                "plugin_id": info.plugin_id,
                "label": info.label,
                "visualization_name": f"plugin:{info.plugin_id}",
            }
            for info in plugins
        ]

    def build_source_plugin_grid_cell(
        self,
        plugin_id: str,
        existing_cell: Dict[str, Any],
        plugin_options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        plugin = str(plugin_id or "").strip()
        if not plugin:
            raise ValueError("Missing plugin")
        existing = dict(existing_cell or {})
        meta = self.source_plugin_context_for_cell(existing)
        schema = plugin_options_schema(plugin, meta)
        raw_options = (
            plugin_options
            if plugin_options is not None
            else dict(existing.get("plugin_options", {}) or {})
        )
        options = normalize_plugin_options(schema, raw_options)
        tile = render_source_plugin_tile(
            self.campaign_path, plugin, meta, options=options
        )

        source_fields = dict(meta.get("source_fields", {}) or {})
        tile.update({k: v for k, v in source_fields.items() if v})
        source_key = str(source_fields.get("_source_key", "") or "")
        tile["_source_keys"] = [source_key] if source_key else []
        tile["_source_fields_list"] = [source_fields] if source_fields else []
        tile["variable_id"] = str(
            existing.get("variable_id", "") or meta.get("variable_id", "") or ""
        )
        tile["variable_name"] = str(
            existing.get("variable_name", "")
            or meta.get("variable_name", "")
            or tile.get("display_title", "")
            or plugin
        )
        tile["plugin_options_schema"] = schema
        tile["plugin_options"] = options
        tile["plugin_scope"] = "source"
        return tile

    def plugin_visualization_names_for_variable(
        self,
        variable_id: str,
        source_filter: Optional[Dict[str, Any]] = None,
        extra_filter: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        candidate = self.plugin_candidate(
            variable_id, source_filter=source_filter, extra_filter=extra_filter
        )
        if not candidate:
            return []
        return supported_plugin_visualizations(build_plugin_meta(candidate))

    def visualization_names_with_plugins(
        self,
        variable_id: str,
        source_filter: Optional[Dict[str, Any]] = None,
        extra_filter: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        base_names = self.db.distinct_visualization_names_for_variable(
            variable_id, extra_filter=extra_filter
        )
        plugin_names = self.plugin_visualization_names_for_variable(
            variable_id,
            source_filter=source_filter,
            extra_filter=extra_filter,
        )
        return self.merge_visualization_names(base_names, plugin_names)

    def update_2d_display_title(
        self, cell: Dict[str, Any], variable_id: str, label: str
    ) -> None:
        media_type = str(cell.get("media_type", "") or "")
        if media_type not in {"image", "image_sequence", "video"}:
            cell["display_title"] = str(label or "")
            cell["scalar_field_colorbar_min"] = ""
            cell["scalar_field_colorbar_max"] = ""
            return

        title_min: Optional[float] = None
        title_max: Optional[float] = None
        if self.is_scalar_field_cell(cell):
            representation_id = str(
                cell.get("selected_visualization", "")
                or cell.get("visualization_name", "")
                or ""
            )
            fmin, fmax = self.source_extrema_for_title(
                variable_id,
                self.source_filter_from_cell(cell),
                representation_id=representation_id,
            )
            if fmin is None or fmax is None:
                fmin, fmax = self.valid_title_extrema(
                    cell.get("min", None), cell.get("max", None)
                )
            title_min, title_max = fmin, fmax
        else:
            fmin, fmax = self.valid_title_extrema(
                cell.get("min", None), cell.get("max", None)
            )
            if fmin is None or fmax is None:
                fmin, fmax = self.source_extrema_for_title(
                    variable_id,
                    self.source_filter_from_cell(cell),
                )

        if fmin is None or fmax is None:
            cell["display_title"] = str(label or "")
        else:
            cell["display_title"] = f"{label} [{fmt(fmin)}, {fmt(fmax)}]"

        cell["scalar_field_colorbar_min"] = ""
        cell["scalar_field_colorbar_max"] = ""
        if self.is_scalar_field_cell(cell):
            settings = self.normalize_scalar_field_settings(
                cell.get("scalar_field_settings", {})
            )
            if not bool(settings.get("range_auto", True)):
                bar_min = self.finite_float(settings.get("min", None))
                bar_max = self.finite_float(settings.get("max", None))
            else:
                bar_min, bar_max = title_min, title_max
            if bar_min is not None and bar_max is not None:
                cell["scalar_field_colorbar_min"] = fmt(bar_min)
                cell["scalar_field_colorbar_max"] = fmt(bar_max)

    def is_generated_plot1d_cell(self, cell: Dict[str, Any]) -> bool:
        if str(cell.get("media_type", "") or "") != "plot1d":
            return False
        selected_vis = str(
            cell.get("selected_visualization", "")
            or cell.get("visualization_name", "")
            or ""
        ).strip()
        visualization_name = str(
            cell.get("visualization_name", "") or selected_vis
        ).strip()
        return (
            selected_vis == GENERATED_SCALAR_PLOT_VIS
            or visualization_name == GENERATED_SCALAR_PLOT_VIS
        )

    def scalar_colormap(self, value: Any) -> str:
        name = str(value or "viridis").strip().lower()
        return name if name in SCALAR_FIELD_COLORMAPS else "viridis"

    def scalar_colormap_gradient(self, value: Any) -> str:
        name = self.scalar_colormap(value)
        return SCALAR_FIELD_COLORMAP_CSS_GRADIENTS.get(
            name,
            SCALAR_FIELD_COLORMAP_CSS_GRADIENTS.get("viridis", ""),
        )

    @staticmethod
    def scalar_field_background(value: Any) -> str:
        return "white" if str(value or "").strip().lower() == "white" else "black"

    def normalize_scalar_field_settings(
        self, raw_settings: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        raw = dict(raw_settings or {})
        background = self.scalar_field_background(raw.get("background", "black"))
        range_mode = str(raw.get("range_mode", "") or "").strip().lower()
        range_auto = raw.get("range_auto", None)
        if range_auto is None:
            range_auto = range_mode != "manual"
        range_auto = self.to_bool(range_auto, True)
        min_value = self.finite_float(raw.get("min", None))
        max_value = self.finite_float(raw.get("max", None))
        if (
            range_auto
            or min_value is None
            or max_value is None
            or min_value >= max_value
        ):
            min_value = None
            max_value = None
            range_auto = True

        return {
            "colormap": self.scalar_colormap(raw.get("colormap", "viridis")),
            "colorbar_gradient": self.scalar_colormap_gradient(
                raw.get("colormap", "viridis")
            ),
            "background": background,
            "background_color": "#ffffff" if background == "white" else "#000000",
            "foreground_color": "#111111" if background == "white" else "#ffffff",
            "range_auto": range_auto,
            "range_mode": "auto" if range_auto else "manual",
            "min": min_value,
            "max": max_value,
            "show_colorbar": self.to_bool(raw.get("show_colorbar", False), False),
            "show_axes": self.to_bool(raw.get("show_axes", False), False),
        }

    def is_scalar_field_cell(self, cell: Dict[str, Any]) -> bool:
        variable_type = str(cell.get("variable_type", "") or "").strip()
        payload_type = str(cell.get("payload_type", "") or "").strip().upper()
        item_type = str(cell.get("visualization_item_type", "") or "").strip().upper()
        return (
            variable_type == SCALAR_FIELD_VARIABLE_TYPE
            or payload_type == "SCALAR_FIELD"
            or item_type == "SCALAR_FIELD"
        )

    def existing_scalar_field_settings(
        self, existing_cell: Optional[Dict[str, Any]], variable_id: str
    ) -> Dict[str, Any]:
        if not isinstance(existing_cell, dict):
            return self.normalize_scalar_field_settings()
        existing_var = str(
            existing_cell.get("variable_id", "")
            or existing_cell.get("variable_name", "")
            or ""
        )
        if existing_var != str(variable_id or ""):
            return self.normalize_scalar_field_settings()
        return self.normalize_scalar_field_settings(
            existing_cell.get("scalar_field_settings", {})
        )

    def load_scalar_field_settings_dialog(self, idx: int, reset: bool = False) -> None:
        cells = self.normalize_grid_cells(self.state.gridCells)
        if not self.is_valid_grid_index(idx):
            return
        cell = dict(cells[idx] or {})
        if not self.is_scalar_field_cell(cell):
            return

        raw_settings = (
            {} if reset else dict(cell.get("scalar_field_settings", {}) or {})
        )
        settings = self.normalize_scalar_field_settings(raw_settings)
        self.state.scalarFieldSettingsCellIndex = idx
        self.state.scalarFieldSettingsTitle = str(
            cell.get("variable_name", "") or f"Cell {idx + 1}"
        )
        self.state.scalarFieldSettingsStatus = ""
        self.state.scalarFieldSettingsStatusIsError = False
        self.state.scalarFieldSettingsColormap = str(
            settings.get("colormap", "viridis") or "viridis"
        )
        self.state.scalarFieldSettingsBackground = str(
            settings.get("background", "black") or "black"
        )
        self.state.scalarFieldSettingsRangeAuto = bool(settings.get("range_auto", True))
        self.state.scalarFieldSettingsMin = self.settings_value_text(
            settings.get("min", None)
        )
        self.state.scalarFieldSettingsMax = self.settings_value_text(
            settings.get("max", None)
        )
        self.state.scalarFieldSettingsShowColorbar = bool(
            settings.get("show_colorbar", False)
        )
        self.state.scalarFieldSettingsShowAxes = bool(settings.get("show_axes", False))
        self.state.showScalarFieldSettingsModal = True

    def load_plot_settings_dialog(self, idx: int, reset: bool = False) -> None:
        cells = self.normalize_grid_cells(self.state.gridCells)
        if not self.is_valid_grid_index(idx):
            return
        cell = dict(cells[idx] or {})
        if str(cell.get("media_type", "") or "") != "plot1d":
            return

        raw_settings = {} if reset else dict(cell.get("plot_settings", {}) or {})
        settings = self.normalize_plot_settings(cell, raw_settings)
        self.state.plotSettingsCellIndex = idx
        self.state.plotSettingsTitle = str(
            cell.get("variable_name", "") or f"Cell {idx + 1}"
        )
        self.state.plotSettingsStatus = ""
        self.state.plotSettingsCanPluginOptions = is_plugin_visualization(
            str(
                cell.get("selected_visualization", "")
                or cell.get("visualization_name", "")
                or ""
            )
        )
        self.state.plotSettingsXAuto = bool(settings.get("x_auto", True))
        self.state.plotSettingsXMin = self.settings_value_text(
            settings.get("x_min", None)
        )
        self.state.plotSettingsXMax = self.settings_value_text(
            settings.get("x_max", None)
        )
        self.state.plotSettingsXScale = str(
            settings.get("x_scale", "linear") or "linear"
        )
        self.state.plotSettingsYAuto = bool(settings.get("y_auto", True))
        self.state.plotSettingsYMin = self.settings_value_text(
            settings.get("y_min", None)
        )
        self.state.plotSettingsYMax = self.settings_value_text(
            settings.get("y_max", None)
        )
        self.state.plotSettingsYScale = str(
            settings.get("y_scale", "linear") or "linear"
        )
        self.state.plotSettingsLineWidth = float(settings.get("line_width", 2.5) or 2.5)
        self.state.plotSettingsShowGrid = bool(settings.get("show_grid", True))
        self.state.plotSettingsShowCursor = bool(settings.get("show_cursor", True))
        self.state.plotSettingsBackgroundColor = self.clean_plot_color(
            settings.get("background_color", ""), "#ffffff"
        )
        self.state.plotSettingsGridColor = self.clean_plot_color(
            settings.get("grid_color", ""), "#e8e8e8"
        )
        self.state.plotSettingsCursorColor = self.clean_plot_color(
            settings.get("cursor_color", ""), "#111111"
        )
        self.state.plotSettingsSeriesRows = self.plot_series_rows_for_tile(
            cell, settings
        )
        self.state.showPlotSettingsModal = True

    def load_plugin_options_dialog(self, idx: int, reset: bool = False) -> None:
        cells = self.normalize_grid_cells(self.state.gridCells)
        if not self.is_valid_grid_index(idx):
            return
        cell = dict(cells[idx] or {})
        selected_vis = str(
            cell.get("selected_visualization", "")
            or cell.get("visualization_name", "")
            or ""
        )
        if not is_plugin_visualization(selected_vis):
            return

        schema = list(cell.get("plugin_options_schema", []) or [])
        options = {} if reset else dict(cell.get("plugin_options", {}) or {})
        options = normalize_plugin_options(schema, options)
        self.state.pluginOptionsCellIndex = idx
        self.state.pluginOptionsTitle = str(
            cell.get("display_title", "")
            or cell.get("variable_name", "")
            or f"Cell {idx + 1}"
        )
        self.state.pluginOptionsStatus = ""
        self.state.pluginOptionsRows = self.plugin_option_rows(schema, options)
        self.state.showPluginOptionsModal = True

    def choose_visualization_default(
        self, vis_names: List[str], preferred_vis: str = ""
    ) -> str:
        preferred = str(preferred_vis or "").strip()
        if preferred and preferred in vis_names:
            return preferred
        if "heatmap" in vis_names:
            return "heatmap"
        return vis_names[0] if vis_names else ""

    def variable_label(self, variable_id: str) -> str:
        item_id = str(variable_id or "").strip()
        labels = dict(self.state.variableLabelsById or {})
        return str(labels.get(item_id, "") or item_id)

    def normalize_scalar_plot_policy(self) -> str:
        policy = str(self.state.scalarPlotPolicy or "always").strip().lower()
        if policy not in {"ask", "always", "never"}:
            policy = "always"
        self.state.scalarPlotPolicy = policy
        return policy

    def clear_pending_scalar_plot(self) -> None:
        self.state.showScalarPlotDialog = False
        self.state.pendingScalarPlotVariableId = ""
        self.state.pendingScalarPlotCellIndex = -1
        self.state.pendingScalarPlotSourceFields = {}
        self.state.pendingScalarPlotSyncSelection = True
        self.state.scalarPlotDialogMessage = ""
        self.state.scalarPlotAlwaysForSession = False

    def build_plugin_grid_cell(
        self,
        variable_id: str,
        plugin_visualization: str,
        source_row: Optional[Dict[str, str]] = None,
        existing_cell: Optional[Dict[str, Any]] = None,
        plugin_options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        var_id = str(variable_id or "").strip()
        plugin_vis = str(plugin_visualization or "").strip()
        plugin_id = plugin_id_from_visualization(plugin_vis)
        if not var_id or not plugin_id:
            raise ValueError("Missing plugin visualization")

        if source_row:
            source_filter = source_filter_from_row(source_row)
        elif existing_cell:
            source_filter = self.source_filter_from_cell(existing_cell)
        else:
            source_filter = self.active_source_filter_for_variable(var_id)

        query_filter = self.active_query_filter()
        candidate = self.plugin_candidate(
            var_id,
            source_filter=source_filter or None,
            extra_filter=query_filter,
        )
        if not candidate:
            raise ValueError("No plugin-compatible source for this variable")

        meta = build_plugin_meta(candidate)
        schema = plugin_options_schema(plugin_id, meta)
        raw_options = (
            plugin_options
            if plugin_options is not None
            else dict((existing_cell or {}).get("plugin_options", {}) or {})
        )
        options = normalize_plugin_options(schema, raw_options)
        tile = render_plugin_tile(
            self.campaign_path, plugin_id, candidate, options=options
        )
        label = self.variable_label(var_id)
        source_fields = self.source_fields_for_assignment(
            var_id, source_row=source_row, candidate=candidate
        )
        if existing_cell and not source_fields.get("_source_key"):
            source_fields["_source_key"] = str(
                existing_cell.get("_source_key", "") or ""
            )
        tile.update({k: v for k, v in source_fields.items() if v})
        source_key = str(source_fields.get("_source_key", "") or "")
        tile["_source_keys"] = [source_key] if source_key else []
        tile["_source_fields_list"] = [source_fields] if source_fields else []
        if str(tile.get("media_type", "") or "") == "plot1d":
            self.assign_plot_series_keys(tile, [source_key] if source_key else [])
            tile["plot_settings"] = self.normalize_plot_settings(
                tile, self.existing_plot_settings(existing_cell, var_id)
            )
        active_filter = (
            and_filter(query_filter, source_filter)
            if query_filter and source_filter
            else (query_filter or source_filter or None)
        )
        base_vis = self.db.distinct_visualization_names_for_variable(
            var_id, extra_filter=active_filter
        )
        plugin_vis_names = supported_plugin_visualizations(meta)
        tile["visualization_options"] = self.merge_visualization_names(
            base_vis, plugin_vis_names
        )
        tile["visualization_name"] = plugin_vis
        tile["selected_visualization"] = plugin_vis
        tile["variable_id"] = var_id
        tile["variable_name"] = label
        tile["plugin_options_schema"] = schema
        tile["plugin_options"] = options
        tile.setdefault("src", "")
        return tile

    def build_grid_cell_for_variable(
        self,
        variable_id: str,
        preferred_vis: str = "",
        source_row: Optional[Dict[str, str]] = None,
        existing_cell: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        cell = empty_grid_cell()
        var_id = str(variable_id or "").strip()
        if not var_id:
            return cell
        label = self.variable_label(var_id)
        scalar_settings = self.existing_scalar_field_settings(existing_cell, var_id)

        qf = self.active_query_filter()
        source_fields: Dict[str, str] = {}
        if source_row:
            source_fields = source_fields_from_row(source_row)
            source_filter = source_filter_from_row(source_row)
        elif existing_cell:
            source_fields = {
                "_source_key": str(existing_cell.get("_source_key", "") or ""),
                "source_dataset": str(existing_cell.get("source_dataset", "") or ""),
                "schema_file_group": str(
                    existing_cell.get("schema_file_group", "") or ""
                ),
                "schema_mode": str(existing_cell.get("schema_mode", "") or ""),
                "producer": str(existing_cell.get("producer", "") or ""),
                "casename": str(existing_cell.get("casename", "") or ""),
                "file": str(existing_cell.get("file", "") or ""),
            }
            source_filter = self.source_filter_from_cell(existing_cell)
        else:
            source_filter = self.active_source_filter_for_variable(var_id)
        active_filter = (
            and_filter(qf, source_filter)
            if qf and source_filter
            else (qf or source_filter or None)
        )
        vis_names = self.visualization_names_with_plugins(
            var_id,
            source_filter=source_filter,
            extra_filter=active_filter,
        )
        if existing_cell and not source_row and source_filter and not vis_names:
            fallback_row = self.first_query_source_row_for_variable(
                var_id, preferred_vis
            )
            if fallback_row:
                source_fields = source_fields_from_row(fallback_row)
                source_filter = source_filter_from_row(fallback_row)
                active_filter = (
                    and_filter(qf, source_filter)
                    if qf and source_filter
                    else (qf or source_filter or None)
                )
                vis_names = self.visualization_names_with_plugins(
                    var_id,
                    source_filter=source_filter,
                    extra_filter=active_filter,
                )

        selected_vis = self.choose_visualization_default(vis_names, preferred_vis)
        if selected_vis and is_plugin_visualization(selected_vis):
            return self.build_plugin_grid_cell(
                var_id,
                selected_vis,
                source_row=source_row,
                existing_cell=existing_cell,
            )

        source_label = self.source_name_for_row(source_row or {})
        no_visualization_note = (
            f"No visualization for source {source_label}"
            if source_label
            else "No visualization types for this variable"
        )
        cell.update(
            {
                "variable_id": var_id,
                "variable_name": label,
                "visualization_name": selected_vis,
                "selected_visualization": selected_vis,
                "visualization_options": vis_names,
                "status": "no-visualizations",
                "note": no_visualization_note,
            }
        )
        cell.update({k: v for k, v in source_fields.items() if v})

        if selected_vis:
            movie_query = (
                and_filter(active_filter, {"visualization_name": selected_vis})
                if active_filter
                else {"visualization_name": selected_vis}
            )
            one = self.db.get_first_movie_tiles_for_variable(
                var_id,
                extra_filter=movie_query,
                limit=1,
                limit_frames=MAX_MOVIE_FRAMES,
                fps=MOVIE_FPS,
                scalar_field_options=scalar_settings,
            )
            if one:
                cell.update(one[0] or {})
                cell.update({k: v for k, v in source_fields.items() if v})
                if self.is_scalar_field_cell(cell):
                    cell["scalar_field_settings"] = scalar_settings
            else:
                cell["status"] = "no-frames"
                cell["note"] = f'No movie for "{selected_vis}"'

        if not str(cell.get("_source_key", "") or ""):
            row = self.source_row_for_cell(cell)
            if row:
                cell.update(source_fields_from_row(row))

        cell["variable_id"] = var_id
        cell["variable_name"] = label
        cell["visualization_name"] = selected_vis
        cell["selected_visualization"] = selected_vis
        cell["visualization_options"] = vis_names
        if self.is_scalar_field_cell(cell):
            cell["scalar_field_settings"] = scalar_settings
        self.update_2d_display_title(cell, var_id, label)
        return cell

    def no_visualization_grid_cell(self, variable_id: str, note: str) -> Dict[str, Any]:
        cell = empty_grid_cell()
        cell["variable_id"] = variable_id
        cell["variable_name"] = self.variable_label(variable_id)
        cell["status"] = "no-visualizations"
        cell["note"] = note
        return cell

    def set_generated_scalar_plot_cell(
        self,
        cell_index: int,
        variable_id: str,
        source_fields: Optional[Dict[str, Any]] = None,
        sync_selection: bool = True,
    ) -> bool:
        try:
            idx = int(cell_index)
        except Exception:
            return False
        if not self.is_valid_grid_index(idx):
            return False

        source_fields = dict(source_fields or {})
        source_filter = self.source_fields_to_filter(variable_id, source_fields)
        try:
            tile = self.db.get_or_create_generated_scalar_plot_tile(
                self.campaign_path,
                variable_id,
                source_filter=source_filter or None,
                extra_filter=self.active_query_filter(),
            )
        except Exception as e:
            tile = {}
            self.state.scalarPlotStatus = (
                f"Scalar plot generation failed: {type(e).__name__}: {e}"
            )

        cells = self.normalize_grid_cells(self.state.gridCells)
        prior_settings = self.existing_plot_settings(cells[idx], variable_id)
        if tile:
            tile.update({k: v for k, v in source_fields.items() if v})
            source_key = str(source_fields.get("_source_key", "") or "")
            self.assign_plot_series_keys(tile, [source_key] if source_key else [])
            tile["plot_settings"] = self.normalize_plot_settings(tile, prior_settings)
            tile["visualization_name"] = str(
                tile.get("visualization_name", "") or GENERATED_SCALAR_PLOT_VIS
            )
            tile["selected_visualization"] = str(
                tile.get("selected_visualization", "") or GENERATED_SCALAR_PLOT_VIS
            )
            tile["visualization_options"] = [GENERATED_SCALAR_PLOT_VIS]
            assign_cell(cells, idx, tile)
            self.state.scalarPlotStatus = ""
        else:
            assign_cell(
                cells,
                idx,
                self.no_visualization_grid_cell(
                    variable_id,
                    "Could not generate scalar plot for this source",
                ),
            )

        self.state.gridCells = self.normalize_grid_cells(cells)
        self.state.activeGridCell = idx
        if sync_selection:
            self.state.selectedVar = variable_id
            self.state.draggedVar = variable_id
        return bool(tile)

    def maybe_handle_generated_scalar_plot(
        self,
        variable_id: str,
        cell_index: int,
        source_row: Optional[Dict[str, str]] = None,
        sync_selection: bool = True,
    ) -> bool:
        source_filter = self.source_filter_for_assignment(
            variable_id, source_row=source_row
        )
        qf = self.active_query_filter()
        active_filter = (
            and_filter(qf, source_filter)
            if qf and source_filter
            else (qf or source_filter or None)
        )
        if self.visualization_names_with_plugins(
            variable_id, source_filter=source_filter, extra_filter=active_filter
        ):
            return False

        candidate = self.db.scalar_plot_candidate(
            variable_id,
            source_filter=source_filter or None,
            extra_filter=qf,
        )
        if not candidate:
            return False

        source_fields = self.source_fields_for_assignment(
            variable_id, source_row=source_row, candidate=candidate
        )
        source_label = str(candidate.get("source_label", "") or "").strip()
        label = self.variable_label(variable_id)
        policy = self.normalize_scalar_plot_policy()
        self.state.activeGridCell = cell_index
        self.state.selectedVar = variable_id
        self.state.draggedVar = variable_id

        if policy == "never":
            cells = self.normalize_grid_cells(self.state.gridCells)
            note = "No saved visualization; scalar plot generation is disabled"
            assign_cell(
                cells, cell_index, self.no_visualization_grid_cell(variable_id, note)
            )
            self.state.gridCells = self.normalize_grid_cells(cells)
            self.state.scalarPlotStatus = note
            return True

        if policy == "always":
            self.set_generated_scalar_plot_cell(
                cell_index,
                variable_id,
                source_fields=source_fields,
                sync_selection=sync_selection,
            )
            return True

        self.state.pendingScalarPlotVariableId = variable_id
        self.state.pendingScalarPlotCellIndex = cell_index
        self.state.pendingScalarPlotSourceFields = source_fields
        self.state.pendingScalarPlotSyncSelection = bool(sync_selection)
        self.state.scalarPlotDialogMessage = (
            f'"{label}" has no saved visualization'
            + (f" for {source_label}" if source_label else "")
            + ". Generate a scalar plot from the raw campaign data?"
        )
        self.state.scalarPlotAlwaysForSession = False
        self.state.showScalarPlotDialog = True
        self.state.scalarPlotStatus = ""
        return True

    def refresh_grid_cells(self):
        cells = self.normalize_grid_cells(self.state.gridCells)
        updated: List[Dict[str, Any]] = []

        for c in cells:
            var_id = str(
                c.get("variable_id", "") or c.get("variable_name", "") or ""
            ).strip()
            if not var_id:
                updated.append(empty_grid_cell_like(c))
                continue

            if is_plugin_visualization(
                str(
                    c.get("visualization_name", "")
                    or c.get("selected_visualization", "")
                    or ""
                )
            ):
                selected_vis = str(
                    c.get("selected_visualization", "")
                    or c.get("visualization_name", "")
                    or ""
                )
                try:
                    if str(c.get("plugin_scope", "") or "") == "source":
                        tile = self.build_source_plugin_grid_cell(
                            plugin_id_from_visualization(selected_vis),
                            c,
                            plugin_options=dict(
                                c.get("plugin_options", {}) or {}
                            ),
                        )
                    else:
                        tile = self.build_plugin_grid_cell(
                            var_id,
                            selected_vis,
                            existing_cell=c,
                            plugin_options=dict(
                                c.get("plugin_options", {}) or {}
                            ),
                        )
                    updated.append(preserve_grid_geometry(tile, c))
                except Exception as e:
                    err_cell = self.no_visualization_grid_cell(
                        var_id, f"{type(e).__name__}: {e}"
                    )
                    updated.append(preserve_grid_geometry(err_cell, c))
                continue

            if str(c.get("visualization_name", "") or "") == GENERATED_SCALAR_PLOT_VIS:
                source_keys = self.source_keys_from_cell(c)
                source_fields_list = self.source_fields_list_from_cell(c)
                try:
                    if len(source_fields_list) > 1:
                        valid_source_fields_list: List[Dict[str, Any]] = []
                        valid_source_keys: List[str] = []
                        for fields in source_fields_list:
                            source_filter = self.source_fields_to_filter(var_id, fields)
                            if self.db.scalar_plot_candidate(
                                var_id,
                                source_filter=source_filter or None,
                                extra_filter=self.active_query_filter(),
                            ):
                                valid_source_fields_list.append(fields)
                                source_key = str(fields.get("_source_key", "") or "")
                                if source_key:
                                    valid_source_keys.append(source_key)
                        source_fields_list = valid_source_fields_list
                        source_keys = valid_source_keys
                        if not source_fields_list:
                            raise ValueError(
                                "Could not regenerate scalar plot for selected sources"
                            )
                        source_filters = [
                            self.source_fields_to_filter(var_id, fields)
                            for fields in source_fields_list
                        ]
                        tile = self.db.get_generated_scalar_plot_tile_for_sources(
                            self.campaign_path,
                            var_id,
                            source_filters=source_filters,
                            extra_filter=self.active_query_filter(),
                        )
                        if not tile:
                            raise ValueError(
                                "Could not regenerate scalar plot for selected sources"
                            )
                        first_fields = source_fields_list[0]
                        tile.update(
                            {
                                k: v
                                for k, v in first_fields.items()
                                if v and k != "_source_key"
                            }
                        )
                        tile["_source_key"] = (
                            source_keys[0]
                            if source_keys
                            else str(first_fields.get("_source_key", "") or "")
                        )
                        tile["_source_keys"] = source_keys
                        tile["_source_fields_list"] = source_fields_list
                    else:
                        source_fields = (
                            source_fields_list[0] if source_fields_list else {}
                        )
                        tile = self.db.get_or_create_generated_scalar_plot_tile(
                            self.campaign_path,
                            var_id,
                            source_filter=self.source_fields_to_filter(
                                var_id, source_fields
                            )
                            or None,
                            extra_filter=self.active_query_filter(),
                        )
                        if not tile:
                            raise ValueError(
                                "Could not regenerate scalar plot for source"
                            )
                        tile.update({k: v for k, v in source_fields.items() if v})
                    tile["visualization_name"] = GENERATED_SCALAR_PLOT_VIS
                    tile["selected_visualization"] = GENERATED_SCALAR_PLOT_VIS
                    tile["visualization_options"] = [GENERATED_SCALAR_PLOT_VIS]
                    self.assign_plot_series_keys(tile, source_keys)
                    tile["plot_settings"] = self.normalize_plot_settings(
                        tile, self.existing_plot_settings(c, var_id)
                    )
                    updated.append(preserve_grid_geometry(tile, c))
                except Exception as e:
                    fallback_row = self.first_query_source_row_for_variable(
                        var_id, GENERATED_SCALAR_PLOT_VIS
                    )
                    try:
                        if not fallback_row:
                            raise e
                        source_fields = source_fields_from_row(fallback_row)
                        source_key = str(source_fields.get("_source_key", "") or "")
                        tile = self.db.get_or_create_generated_scalar_plot_tile(
                            self.campaign_path,
                            var_id,
                            source_filter=self.source_fields_to_filter(
                                var_id, source_fields
                            )
                            or None,
                            extra_filter=self.active_query_filter(),
                        )
                        if not tile:
                            raise e
                        tile.update({k: v for k, v in source_fields.items() if v})
                        tile["visualization_name"] = GENERATED_SCALAR_PLOT_VIS
                        tile["selected_visualization"] = GENERATED_SCALAR_PLOT_VIS
                        tile["visualization_options"] = [GENERATED_SCALAR_PLOT_VIS]
                        tile["_source_keys"] = [source_key] if source_key else []
                        tile["_source_fields_list"] = (
                            [source_fields] if source_fields else []
                        )
                        self.assign_plot_series_keys(
                            tile, [source_key] if source_key else []
                        )
                        tile["plot_settings"] = self.normalize_plot_settings(
                            tile, self.existing_plot_settings(c, var_id)
                        )
                        updated.append(preserve_grid_geometry(tile, c))
                    except Exception as fallback_e:
                        err_cell = self.no_visualization_grid_cell(
                            var_id, f"{type(fallback_e).__name__}: {fallback_e}"
                        )
                        updated.append(preserve_grid_geometry(err_cell, c))
                continue

            preferred_vis = str(c.get("selected_visualization", "") or "")
            try:
                updated.append(
                    preserve_grid_geometry(
                        self.build_grid_cell_for_variable(
                            var_id, preferred_vis=preferred_vis, existing_cell=c
                        ),
                        c,
                    )
                )
            except Exception as e:
                err_cell = empty_grid_cell()
                err_cell["variable_id"] = var_id
                err_cell["variable_name"] = self.variable_label(var_id)
                err_cell["status"] = "error"
                err_cell["note"] = f"{type(e).__name__}: {e}"
                updated.append(preserve_grid_geometry(err_cell, c))

        self.state.gridCells = self.normalize_grid_cells(updated)

        try:
            idx = int(self.state.activeGridCell)
        except Exception:
            idx = -1
        self.state.activeGridCell = idx if self.is_valid_grid_index(idx) else -1

    def cancel_scalar_plot_generation(self, **_):
        self.clear_pending_scalar_plot()

    def confirm_scalar_plot_generation(self, **_):
        var_id = str(self.state.pendingScalarPlotVariableId or "").strip()
        try:
            idx = int(self.state.pendingScalarPlotCellIndex)
        except Exception:
            idx = -1
        source_fields = dict(self.state.pendingScalarPlotSourceFields or {})
        sync_selection = bool(self.state.pendingScalarPlotSyncSelection)

        if bool(self.state.scalarPlotAlwaysForSession):
            self.state.scalarPlotPolicy = "always"

        self.clear_pending_scalar_plot()
        if not var_id or not self.is_valid_grid_index(idx):
            return

        self.set_generated_scalar_plot_cell(
            idx,
            var_id,
            source_fields=source_fields,
            sync_selection=sync_selection,
        )

    def cancel_plot_settings(self, **_):
        self.state.showPlotSettingsModal = False
        self.state.plotSettingsCellIndex = -1
        self.state.plotSettingsStatus = ""
        self.state.plotSettingsCanPluginOptions = False

    def open_plot_settings_plugin_options(self, **_):
        try:
            idx = int(self.state.plotSettingsCellIndex)
        except Exception:
            idx = -1
        if not self.is_valid_grid_index(idx):
            self.state.plotSettingsStatus = "No plot cell selected."
            return

        cells = self.normalize_grid_cells(self.state.gridCells)
        cell = dict(cells[idx] or {})
        selected_vis = str(
            cell.get("selected_visualization", "")
            or cell.get("visualization_name", "")
            or ""
        )
        if not is_plugin_visualization(selected_vis):
            self.state.plotSettingsStatus = (
                "Selected cell is not a plugin visualization."
            )
            return

        self.state.showPlotSettingsModal = False
        self.load_plugin_options_dialog(idx)

    def cancel_plugin_options(self, **_):
        self.state.showPluginOptionsModal = False
        self.state.pluginOptionsCellIndex = -1
        self.state.pluginOptionsStatus = ""
        self.state.pluginOptionsRows = []

    def reset_plugin_options(self, **_):
        try:
            idx = int(self.state.pluginOptionsCellIndex)
        except Exception:
            idx = -1
        if self.is_valid_grid_index(idx):
            self.load_plugin_options_dialog(idx, reset=True)

    def update_plugin_option_value(self, key: str, value: Any, **_):
        target_key = str(key or "").strip()
        if not target_key:
            return
        rows = []
        for raw_row in self.state.pluginOptionsRows or []:
            row = dict(raw_row or {})
            if str(row.get("key", "") or "") == target_key:
                if str(row.get("type", "") or "") == "bool":
                    row["value"] = bool(value)
                else:
                    row["value"] = str(value or "")
            rows.append(row)
        self.state.pluginOptionsRows = rows

    def apply_plugin_options(self, **_):
        try:
            idx = int(self.state.pluginOptionsCellIndex)
        except Exception:
            idx = -1
        if not self.is_valid_grid_index(idx):
            self.state.pluginOptionsStatus = "No plugin cell selected."
            return

        cells = self.normalize_grid_cells(self.state.gridCells)
        cell = dict(cells[idx] or {})
        selected_vis = str(
            cell.get("selected_visualization", "")
            or cell.get("visualization_name", "")
            or ""
        )
        if not is_plugin_visualization(selected_vis):
            self.state.pluginOptionsStatus = (
                "Selected cell is not a plugin visualization."
            )
            return

        var_id = str(
            cell.get("variable_id", "") or cell.get("variable_name", "") or ""
        ).strip()
        if not var_id:
            self.state.pluginOptionsStatus = "Selected cell has no variable."
            return

        options = self.plugin_options_from_rows(
            list(self.state.pluginOptionsRows or [])
        )
        try:
            plugin_id = plugin_id_from_visualization(selected_vis)
            if plugin_scope(plugin_id) == "source":
                new_cell = self.build_source_plugin_grid_cell(
                    plugin_id, cell, plugin_options=options
                )
            else:
                new_cell = self.build_plugin_grid_cell(
                    var_id,
                    selected_vis,
                    existing_cell=cell,
                    plugin_options=options,
                )
            assign_cell(cells, idx, new_cell)
        except Exception as e:
            self.state.pluginOptionsStatus = f"{type(e).__name__}: {e}"
            return

        self.state.gridCells = self.normalize_grid_cells(cells)
        self.state.activeGridCell = idx
        self.state.pluginOptionsStatus = ""
        self.state.showPluginOptionsModal = False

    def cancel_scalar_field_settings(self, **_):
        self.state.showScalarFieldSettingsModal = False
        self.state.scalarFieldSettingsCellIndex = -1
        self.state.scalarFieldSettingsStatus = ""
        self.state.scalarFieldSettingsStatusIsError = False

    def reset_scalar_field_settings(self, **_):
        try:
            idx = int(self.state.scalarFieldSettingsCellIndex)
        except Exception:
            idx = -1
        if self.is_valid_grid_index(idx):
            self.load_scalar_field_settings_dialog(idx, reset=True)

    def apply_scalar_field_settings(self, **_):
        try:
            idx = int(self.state.scalarFieldSettingsCellIndex)
        except Exception:
            idx = -1
        if not self.is_valid_grid_index(idx):
            self.state.scalarFieldSettingsStatus = "No scalar-field cell selected."
            self.state.scalarFieldSettingsStatusIsError = True
            return

        cells = self.normalize_grid_cells(self.state.gridCells)
        cell = dict(cells[idx] or {})
        if not self.is_scalar_field_cell(cell):
            self.state.scalarFieldSettingsStatus = (
                "Selected cell is not a scalar-field visualization."
            )
            self.state.scalarFieldSettingsStatusIsError = True
            return

        colormap = self.scalar_colormap(self.state.scalarFieldSettingsColormap)
        background = self.scalar_field_background(
            self.state.scalarFieldSettingsBackground
        )
        range_auto = bool(self.state.scalarFieldSettingsRangeAuto)
        show_colorbar = bool(self.state.scalarFieldSettingsShowColorbar)
        show_axes = bool(self.state.scalarFieldSettingsShowAxes)
        min_value = self.finite_float(self.state.scalarFieldSettingsMin)
        max_value = self.finite_float(self.state.scalarFieldSettingsMax)
        if not range_auto:
            if min_value is None or max_value is None:
                self.state.scalarFieldSettingsStatus = (
                    "Manual range requires min and max values."
                )
                self.state.scalarFieldSettingsStatusIsError = True
                return
            if min_value >= max_value:
                self.state.scalarFieldSettingsStatus = (
                    "Manual range must have min < max."
                )
                self.state.scalarFieldSettingsStatusIsError = True
                return

        settings = self.normalize_scalar_field_settings(
            {
                "colormap": colormap,
                "background": background,
                "range_auto": range_auto,
                "min": None if range_auto else min_value,
                "max": None if range_auto else max_value,
                "show_colorbar": show_colorbar,
                "show_axes": show_axes,
            }
        )
        cell["scalar_field_settings"] = settings

        var = str(
            cell.get("variable_id", "") or cell.get("variable_name", "") or ""
        ).strip()
        selected_vis = str(
            cell.get("selected_visualization", "")
            or cell.get("visualization_name", "")
            or ""
        ).strip()
        if not var or not selected_vis:
            self.state.scalarFieldSettingsStatus = (
                "Cell is missing a variable or visualization."
            )
            self.state.scalarFieldSettingsStatusIsError = True
            return

        try:
            new_cell = self.build_grid_cell_for_variable(
                var, preferred_vis=selected_vis, existing_cell=cell
            )
            assign_cell(cells, idx, new_cell)
        except Exception as e:
            self.state.scalarFieldSettingsStatus = f"{type(e).__name__}: {e}"
            self.state.scalarFieldSettingsStatusIsError = True
            return

        self.state.gridCells = self.normalize_grid_cells(cells)
        self.state.activeGridCell = idx
        self.state.scalarFieldSettingsStatus = "Applied."
        self.state.scalarFieldSettingsStatusIsError = False

    def reset_plot_settings(self, **_):
        try:
            idx = int(self.state.plotSettingsCellIndex)
        except Exception:
            idx = -1
        if self.is_valid_grid_index(idx):
            self.load_plot_settings_dialog(idx, reset=True)

    def update_plot_background_color(self, color: str, **_):
        self.state.plotSettingsBackgroundColor = self.clean_plot_color(
            color,
            str(self.state.plotSettingsBackgroundColor or "#ffffff"),
        )

    def update_plot_grid_color(self, color: str, **_):
        self.state.plotSettingsGridColor = self.clean_plot_color(
            color,
            str(self.state.plotSettingsGridColor or "#e8e8e8"),
        )

    def update_plot_cursor_color(self, color: str, **_):
        self.state.plotSettingsCursorColor = self.clean_plot_color(
            color,
            str(self.state.plotSettingsCursorColor or "#111111"),
        )

    def update_plot_series_color(self, key: str, color: str, **_):
        target_key = str(key or "")
        rows = []
        for raw_row in self.state.plotSettingsSeriesRows or []:
            row = dict(raw_row or {})
            if str(row.get("key", "") or "") == target_key:
                row["color"] = self.clean_plot_color(
                    color, str(row.get("color", "") or "#1565c0")
                )
            rows.append(row)
        self.state.plotSettingsSeriesRows = rows

    def update_plot_series_line_style(self, key: str, line_style: str, **_):
        target_key = str(key or "")
        rows = []
        for raw_row in self.state.plotSettingsSeriesRows or []:
            row = dict(raw_row or {})
            if str(row.get("key", "") or "") == target_key:
                row["line_style"] = self.clean_line_style(line_style)
            rows.append(row)
        self.state.plotSettingsSeriesRows = rows

    def apply_plot_settings(self, **_):
        try:
            idx = int(self.state.plotSettingsCellIndex)
        except Exception:
            idx = -1
        if not self.is_valid_grid_index(idx):
            self.state.plotSettingsStatus = "No plot cell selected."
            return

        cells = self.normalize_grid_cells(self.state.gridCells)
        cell = dict(cells[idx] or {})
        if str(cell.get("media_type", "") or "") != "plot1d":
            self.state.plotSettingsStatus = "Selected cell is not a 1D plot."
            return

        x_auto = bool(self.state.plotSettingsXAuto)
        y_auto = bool(self.state.plotSettingsYAuto)
        x_min = self.finite_float(self.state.plotSettingsXMin)
        x_max = self.finite_float(self.state.plotSettingsXMax)
        y_min = self.finite_float(self.state.plotSettingsYMin)
        y_max = self.finite_float(self.state.plotSettingsYMax)
        x_scale = str(self.state.plotSettingsXScale or "linear").strip().lower()
        y_scale = str(self.state.plotSettingsYScale or "linear").strip().lower()
        if x_scale not in {"linear", "log"}:
            x_scale = "linear"
        if y_scale not in {"linear", "log"}:
            y_scale = "linear"

        if not x_auto:
            if x_min is None or x_max is None:
                self.state.plotSettingsStatus = (
                    "Manual X range requires min and max values."
                )
                return
            if x_min >= x_max:
                self.state.plotSettingsStatus = "Manual X range must have min < max."
                return
        if not y_auto:
            if y_min is None or y_max is None:
                self.state.plotSettingsStatus = (
                    "Manual Y range requires min and max values."
                )
                return
            if y_min >= y_max:
                self.state.plotSettingsStatus = "Manual Y range must have min < max."
                return

        if x_scale == "log":
            if not self.axis_has_positive_data(cell, "x"):
                self.state.plotSettingsStatus = (
                    "X log scale requires positive X values."
                )
                return
            if not x_auto and (
                x_min is None or x_max is None or x_min <= 0 or x_max <= 0
            ):
                self.state.plotSettingsStatus = "Manual X log range must be positive."
                return
        if y_scale == "log":
            if not self.axis_has_positive_data(cell, "y"):
                self.state.plotSettingsStatus = (
                    "Y log scale requires positive Y values."
                )
                return
            if not y_auto and (
                y_min is None or y_max is None or y_min <= 0 or y_max <= 0
            ):
                self.state.plotSettingsStatus = "Manual Y log range must be positive."
                return

        line_width = self.finite_float(self.state.plotSettingsLineWidth)
        if line_width is None:
            self.state.plotSettingsStatus = "Line width must be a number."
            return
        line_width = max(0.5, min(8.0, line_width))
        background_color = self.clean_plot_color(
            self.state.plotSettingsBackgroundColor, "#ffffff"
        )
        grid_color = self.clean_plot_color(self.state.plotSettingsGridColor, "#e8e8e8")
        cursor_color = self.clean_plot_color(
            self.state.plotSettingsCursorColor, "#111111"
        )

        series_colors: Dict[str, str] = {}
        series_styles: Dict[str, Dict[str, str]] = {}
        current_settings = self.normalize_plot_settings(
            cell, cell.get("plot_settings", {})
        )
        current_colors = current_settings.get("series_colors", {})
        current_colors = current_colors if isinstance(current_colors, dict) else {}
        current_styles = current_settings.get("series_styles", {})
        current_styles = current_styles if isinstance(current_styles, dict) else {}
        for row in self.state.plotSettingsSeriesRows or []:
            item = dict(row or {})
            key = str(item.get("key", "") or "")
            if not key:
                continue
            current_style = current_styles.get(key, {})
            current_style = current_style if isinstance(current_style, dict) else {}
            color = self.clean_plot_color(
                item.get("color", ""),
                str(
                    current_style.get("color", "")
                    or current_colors.get(key, "")
                    or "#1565c0"
                ),
            )
            line_style = self.clean_line_style(
                item.get("line_style", current_style.get("line_style", "solid"))
            )
            series_colors[key] = color
            series_styles[key] = {
                "color": color,
                "line_style": line_style,
            }

        cell["plot_settings"] = self.normalize_plot_settings(
            cell,
            {
                "x_auto": x_auto,
                "x_min": None if x_auto else x_min,
                "x_max": None if x_auto else x_max,
                "x_scale": x_scale,
                "y_auto": y_auto,
                "y_min": None if y_auto else y_min,
                "y_max": None if y_auto else y_max,
                "y_scale": y_scale,
                "series_colors": series_colors,
                "series_styles": series_styles,
                "line_width": line_width,
                "show_grid": bool(self.state.plotSettingsShowGrid),
                "show_cursor": bool(self.state.plotSettingsShowCursor),
                "background_color": background_color,
                "grid_color": grid_color,
                "cursor_color": cursor_color,
            },
        )
        cells[idx] = cell
        self.state.gridCells = self.normalize_grid_cells(cells)
        self.state.activeGridCell = idx
        self.state.plotSettingsStatus = ""
        self.state.showPlotSettingsModal = False
