import math
import re
from typing import Any, Dict, List, Optional, Tuple

from application import NavigationNode, SeuratApplication
from config import MAX_MOVIE_FRAMES, MOVIE_FPS
from db import (
    GENERATED_SCALAR_PLOT_VIS,
    SCALAR_FIELD_COLORMAP_CSS_GRADIENTS,
    SCALAR_FIELD_COLORMAPS,
    SCALAR_FIELD_VARIABLE_TYPE,
    VISUALIZATION_PAYLOAD_VARIABLE_TYPES,
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
from query_parser import and_filter, mongo_filter_matches, python_query_to_filters
from state_init import clear_right_panes, fmt


def _variable_groups_from_navigation(nodes: List[NavigationNode]) -> List[Dict[str, Any]]:
    groups: List[Dict[str, Any]] = []
    for node in nodes:
        variables: List[Dict[str, str]] = []
        for child in node.get("children", []) or []:
            if child.get("kind") != "variable":
                continue
            resource = child.get("resource") or {}
            variable_id = str(resource.get("variable_id", "") or "")
            if not variable_id:
                continue
            variables.append(
                {
                    "id": variable_id,
                    "name": str(resource.get("name", "") or ""),
                    "label": str(
                        resource.get("label", "")
                        or child.get("label", "")
                        or variable_id
                    ),
                    "path": str(resource.get("path", "") or ""),
                    "source_dataset": str(resource.get("source_dataset", "") or ""),
                }
            )
        if variables:
            groups.append({"name": str(node.get("label", "") or ""), "variables": variables})
    return groups


def attach_controllers(
    server,
    db,
    collection,
    parse_campaign,
    campaign_path: str,
    image_association_schema_path: str = "",
):
    state, ctrl = server.state, server.controller
    application = SeuratApplication(db)
    GRID_MIN_ROWS = 1
    GRID_MIN_COLS = 1
    GRID_MAX_ROWS = 8
    GRID_MAX_COLS = 8
    GRID_HEADER_HEIGHT = 32
    GRID_MIN_TRACK_WEIGHT = 0.05
    GRID_MAX_TRACK_WEIGHT = 100.0

    def active_query_filter() -> Optional[Dict[str, Any]]:
        query_filter = state.queryFilter or None
        source_restriction = state.querySourceRestrictionFilter or None
        if query_filter and source_restriction:
            return and_filter(query_filter, source_restriction)
        return query_filter or source_restriction or None

    def refresh_variable_list():
        navigation = application.get_navigation(
            {
                "view": "variables",
                "query": active_query_filter() or {},
                "only_visualized": bool(state.showOnlyVisualizedVars),
                "parent_id": None,
            }
        )
        grouped = _variable_groups_from_navigation(navigation)
        state.variableGroups = grouped
        variables = [v for g in grouped for v in (g.get("variables") or []) if isinstance(v, dict)]
        state.variableNames = [str(v.get("id", "") or "") for v in variables if str(v.get("id", "") or "")]
        state.variableLabelsById = {
            str(v.get("id", "") or ""): str(v.get("label", "") or v.get("name", "") or v.get("id", "") or "")
            for v in variables
            if str(v.get("id", "") or "")
        }
        existing_collapsed = dict(state.variableGroupCollapsed or {})
        valid_group_names = {str(g.get("name", "")) for g in grouped}
        state.variableGroupCollapsed = {
            name: bool(existing_collapsed.get(name, False))
            for name in valid_group_names
            if name
        }
        state.dbOk = db.ok
        state.dbStatus = "Connected" if db.ok else f"DB error: {db.last_error}"

    def all_source_rows() -> List[Dict[str, Any]]:
        return list(state.sourceRowsAll or state.sourceRows or [])

    def source_row_keys(rows: Optional[List[Dict[str, Any]]] = None) -> List[str]:
        source_rows = all_source_rows() if rows is None else rows
        return [str(r.get("_key", "")) for r in source_rows if str(r.get("_key", ""))]

    def visible_source_row_keys() -> List[str]:
        return source_row_keys(list(state.sourceRows or []))

    def update_selected_source_label():
        total = len(all_source_rows())
        shown = len(state.sourceRows or [])
        selected = len(state.selectedSourceKeys or [])
        if total <= 0:
            state.selectedSourceLabel = "No sources"
        elif selected <= 0:
            state.selectedSourceLabel = "No sources selected"
        else:
            state.selectedSourceLabel = f"{selected} of {total} selected"
        if total > 0 and shown != total:
            state.selectedSourceLabel = f"{state.selectedSourceLabel} · {shown} shown"

    def select_source_key(key: str):
        k = str(key or "")
        state.selectedSourceKeys = [k] if k and k in source_row_keys() else []
        update_selected_source_label()

    def select_first_source():
        keys = visible_source_row_keys()
        select_source_key(keys[0] if keys else "")

    def source_filter_from_row(row: Dict[str, str]) -> Dict[str, str]:
        filt: Dict[str, str] = {}
        variable_id = str(row.get("variable_id", "") or "")
        if variable_id:
            filt["variable_id"] = variable_id

        schema_file_group = str(row.get("schema_file_group", "") or "")
        schema_mode = str(row.get("schema_mode", "") or "")
        if schema_file_group and schema_mode == "file_per_timestep":
            filt["schema_file_group"] = schema_file_group
            filt["schema_mode"] = schema_mode
            return filt

        source_dataset = str(row.get("source_dataset", "") or "")
        if source_dataset:
            filt["source_dataset"] = source_dataset
            return filt

        producer = str(row.get("producer", "") or "")
        casename = str(row.get("casename", "") or "")
        file_name = str(row.get("file", "") or "")
        if producer or casename or file_name:
            filt["producer"] = producer
            filt["casename"] = casename
        if file_name:
            filt["file"] = file_name
        return filt

    def source_row_for_key(key: str) -> Dict[str, str]:
        k = str(key or "")
        if not k:
            return {}
        return next((r for r in all_source_rows() if str(r.get("_key", "")) == k), {})

    def source_fields_from_row(row: Dict[str, str]) -> Dict[str, str]:
        if not row:
            return {}
        return {
            "_source_key": str(row.get("_key", "") or ""),
            "source_dataset": str(row.get("source_dataset", "") or ""),
            "schema_file_group": str(row.get("schema_file_group", "") or ""),
            "schema_mode": str(row.get("schema_mode", "") or ""),
            "producer": str(row.get("producer", "") or ""),
            "casename": str(row.get("casename", "") or ""),
            "file": str(row.get("file", "") or ""),
        }

    def normalize_source_keys(raw_keys) -> List[str]:
        if isinstance(raw_keys, str):
            items = [raw_keys]
        elif isinstance(raw_keys, (list, tuple)):
            items = list(raw_keys)
        else:
            items = []

        keys: List[str] = []
        for raw_key in items:
            key = str(raw_key or "").strip()
            if key and key not in keys:
                keys.append(key)
        return keys

    def source_keys_from_cell(cell: Dict[str, Any]) -> List[str]:
        keys = normalize_source_keys(cell.get("_source_keys", []))
        key = str(cell.get("_source_key", "") or "").strip()
        if key and key not in keys:
            keys.insert(0, key)
        return keys

    def source_rows_for_keys(keys: List[str]) -> List[Dict[str, str]]:
        rows: List[Dict[str, str]] = []
        for key in normalize_source_keys(keys):
            row = source_row_for_key(key)
            if row:
                rows.append(row)
        return rows

    def source_fields_list_from_cell(cell: Dict[str, Any]) -> List[Dict[str, Any]]:
        raw_items = cell.get("_source_fields_list", [])
        fields_list: List[Dict[str, Any]] = []
        if isinstance(raw_items, list):
            for raw_item in raw_items:
                if isinstance(raw_item, dict):
                    fields = {
                        "_source_key": str(raw_item.get("_source_key", "") or ""),
                        "source_dataset": str(raw_item.get("source_dataset", "") or ""),
                        "schema_file_group": str(raw_item.get("schema_file_group", "") or ""),
                        "schema_mode": str(raw_item.get("schema_mode", "") or ""),
                        "producer": str(raw_item.get("producer", "") or ""),
                        "casename": str(raw_item.get("casename", "") or ""),
                        "file": str(raw_item.get("file", "") or ""),
                    }
                    if any(fields.values()):
                        fields_list.append(fields)

        if not fields_list:
            for row in source_rows_for_keys(source_keys_from_cell(cell)):
                fields = source_fields_from_row(row)
                if fields:
                    fields_list.append(fields)

        if not fields_list:
            fields = {
                "_source_key": str(cell.get("_source_key", "") or ""),
                "source_dataset": str(cell.get("source_dataset", "") or ""),
                "schema_file_group": str(cell.get("schema_file_group", "") or ""),
                "schema_mode": str(cell.get("schema_mode", "") or ""),
                "producer": str(cell.get("producer", "") or ""),
                "casename": str(cell.get("casename", "") or ""),
                "file": str(cell.get("file", "") or ""),
            }
            if any(fields.values()):
                fields_list.append(fields)
        return fields_list

    def source_filter_from_cell(cell: Dict[str, Any]) -> Dict[str, str]:
        schema_file_group = str(cell.get("schema_file_group", "") or "")
        schema_mode = str(cell.get("schema_mode", "") or "")
        if schema_file_group and schema_mode == "file_per_timestep":
            filt = {"schema_file_group": schema_file_group, "schema_mode": schema_mode}
            variable_id = str(cell.get("variable_id", "") or "")
            if variable_id:
                filt["variable_id"] = variable_id
            return filt

        source_dataset = str(cell.get("source_dataset", "") or "")
        if source_dataset:
            filt = {"source_dataset": source_dataset}
            variable_id = str(cell.get("variable_id", "") or "")
            if variable_id:
                filt["variable_id"] = variable_id
            return filt

        producer = str(cell.get("producer", "") or "")
        casename = str(cell.get("casename", "") or "")
        file_name = str(cell.get("file", "") or "")
        if producer or casename or file_name:
            filt = {"producer": producer, "casename": casename}
            if file_name:
                filt["file"] = file_name
            return filt
        return {}

    def source_row_for_cell(cell: Dict[str, Any]) -> Dict[str, str]:
        key = str(cell.get("_source_key", "") or "")
        if key:
            row = source_row_for_key(key)
            if row:
                return row

        source_dataset = str(cell.get("source_dataset", "") or "")
        schema_file_group = str(cell.get("schema_file_group", "") or "")
        schema_mode = str(cell.get("schema_mode", "") or "")
        producer = str(cell.get("producer", "") or "")
        casename = str(cell.get("casename", "") or "")
        file_name = str(cell.get("file", "") or "")
        for row in all_source_rows():
            if (
                schema_file_group
                and schema_mode
                and str(row.get("schema_file_group", "") or "") == schema_file_group
                and str(row.get("schema_mode", "") or "") == schema_mode
            ):
                return row
            if source_dataset and str(row.get("source_dataset", "") or "") == source_dataset:
                return row
            if (
                (producer or casename or file_name)
                and str(row.get("producer", "") or "") == producer
                and str(row.get("casename", "") or "") == casename
                and str(row.get("file", "") or "") == file_name
            ):
                return row
        return {}

    def source_key_for_fields(row: Dict[str, Any]) -> str:
        schema_file_group = str(row.get("schema_file_group", "") or "")
        schema_mode = str(row.get("schema_mode", "") or "")
        if schema_file_group and schema_mode == "file_per_timestep":
            return f"schema|{row.get('variable_id', '')}|{schema_file_group}"
        return (
            "|".join(
                str(row.get(key, "") or "")
                for key in ("variable_id", "source_dataset", "producer", "casename", "file")
            ).strip("|")
            or str(row.get("source_dataset", "") or "")
            or f"{row.get('producer', '')}|{row.get('casename', '')}|{row.get('file', '')}"
        )

    def visualization_names_for_source_filter(variable_id: str, source_filter: Dict[str, Any]) -> List[str]:
        qf = active_query_filter()
        active_filter = and_filter(qf, source_filter) if qf and source_filter else (qf or source_filter or None)
        return visualization_names_with_plugins(variable_id, source_filter=source_filter, extra_filter=active_filter)

    def merge_visualization_names(base_names: List[str], plugin_names: List[str]) -> List[str]:
        out: List[str] = []
        for raw_name in list(base_names or []) + list(plugin_names or []):
            name = str(raw_name or "").strip()
            if name and name not in out:
                out.append(name)
        return out

    plugin_source_variables_cache: Dict[Tuple[str, str, str, str, str, str], List[Dict[str, Any]]] = {}

    def plugin_source_variables_cache_key(source_fields: Dict[str, Any]) -> Tuple[str, str, str, str, str, str]:
        fields = dict(source_fields or {})
        return tuple(
            str(fields.get(key, "") or "")
            for key in ("source_dataset", "schema_file_group", "schema_mode", "producer", "casename", "file")
        )

    def plugin_source_variables(candidate: Dict[str, Any]) -> List[Dict[str, Any]]:
        source_fields = dict((candidate or {}).get("source_fields", {}) or {})
        cache_key = plugin_source_variables_cache_key(source_fields)
        if cache_key in plugin_source_variables_cache:
            return list(plugin_source_variables_cache[cache_key])

        query: Dict[str, Any] = {"variable_type": "variable"}
        source_dataset = str(source_fields.get("source_dataset", "") or "")
        schema_file_group = str(source_fields.get("schema_file_group", "") or "")
        schema_mode = str(source_fields.get("schema_mode", "") or "")
        if schema_file_group and schema_mode == "file_per_timestep":
            query["schema_file_group"] = schema_file_group
            query["schema_mode"] = schema_mode
        elif source_dataset:
            query["source_dataset"] = source_dataset
        else:
            for key in ("producer", "casename", "file"):
                value = str(source_fields.get(key, "") or "")
                if value:
                    query[key] = value

        proj = {
            "_id": 0,
            "variable_id": 1,
            "variable_name": 1,
            "variable_path": 1,
            "source_dataset": 1,
            "metadata": 1,
        }
        variables: List[Dict[str, Any]] = []
        try:
            for doc in db.collection.find(query, proj):
                variable_id = str(doc.get("variable_id", "") or "")
                variable_name = str(doc.get("variable_name", "") or variable_id)
                variable_path = str(doc.get("variable_path", "") or "")
                if not variable_id and not variable_name and not variable_path:
                    continue
                metadata = doc.get("metadata", {}) or {}
                if not isinstance(metadata, dict):
                    metadata = {}
                variables.append(
                    {
                        "variable_id": variable_id,
                        "variable_name": variable_name,
                        "variable_path": variable_path,
                        "source_dataset": str(doc.get("source_dataset", "") or ""),
                        "metadata": metadata,
                    }
                )
        except Exception:
            variables = []

        plugin_source_variables_cache[cache_key] = list(variables)
        return variables

    def plugin_candidate(
        variable_id: str,
        source_filter: Optional[Dict[str, Any]] = None,
        extra_filter: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        try:
            candidate = db.scalar_plot_candidate(
                variable_id,
                source_filter=source_filter or None,
                extra_filter=extra_filter,
            )
            if candidate:
                candidate["source_variables"] = plugin_source_variables(candidate)
            return candidate
        except Exception:
            return {}

    def source_plugin_context_for_cell(cell: Dict[str, Any]) -> Dict[str, Any]:
        source_fields_items = source_fields_list_from_cell(cell)
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

        source_variables = plugin_source_variables({"source_fields": source_fields}) if source_fields else []
        metadata = cell.get("metadata", {}) or {}
        if not isinstance(metadata, dict):
            metadata = {}
        return {
            "variable_id": str(cell.get("variable_id", "") or ""),
            "variable_name": str(cell.get("variable_name", "") or cell.get("variable_id", "") or ""),
            "variable_path": str(cell.get("variable_path", "") or ""),
            "source_dataset": str(source_fields.get("source_dataset", "") or cell.get("source_dataset", "") or ""),
            "source_fields": source_fields,
            "source_variables": source_variables,
            "metadata": dict(metadata),
            "ndims": None,
            "steps_count": 1,
            "shape": [],
            "min": cell.get("min", None),
            "max": cell.get("max", None),
        }

    def source_plugin_menu_entries_for_cell(cell: Dict[str, Any]) -> List[Dict[str, str]]:
        try:
            meta = source_plugin_context_for_cell(cell)
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
        plugin_id: str,
        existing_cell: Dict[str, Any],
        plugin_options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        plugin = str(plugin_id or "").strip()
        if not plugin:
            raise ValueError("Missing plugin")
        existing = dict(existing_cell or {})
        meta = source_plugin_context_for_cell(existing)
        schema = plugin_options_schema(plugin, meta)
        raw_options = (
            plugin_options
            if plugin_options is not None
            else dict(existing.get("plugin_options", {}) or {})
        )
        options = normalize_plugin_options(schema, raw_options)
        tile = render_source_plugin_tile(campaign_path, plugin, meta, options=options)

        source_fields = dict(meta.get("source_fields", {}) or {})
        tile.update({k: v for k, v in source_fields.items() if v})
        source_key = str(source_fields.get("_source_key", "") or "")
        tile["_source_keys"] = [source_key] if source_key else []
        tile["_source_fields_list"] = [source_fields] if source_fields else []
        tile["variable_id"] = str(existing.get("variable_id", "") or meta.get("variable_id", "") or "")
        tile["variable_name"] = str(existing.get("variable_name", "") or meta.get("variable_name", "") or tile.get("display_title", "") or plugin)
        tile["plugin_options_schema"] = schema
        tile["plugin_options"] = options
        tile["plugin_scope"] = "source"
        return tile

    def plugin_visualization_names_for_variable(
        variable_id: str,
        source_filter: Optional[Dict[str, Any]] = None,
        extra_filter: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        candidate = plugin_candidate(variable_id, source_filter=source_filter, extra_filter=extra_filter)
        if not candidate:
            return []
        return supported_plugin_visualizations(build_plugin_meta(candidate))

    def visualization_names_with_plugins(
        variable_id: str,
        source_filter: Optional[Dict[str, Any]] = None,
        extra_filter: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        base_names = db.distinct_visualization_names_for_variable(variable_id, extra_filter=extra_filter)
        plugin_names = plugin_visualization_names_for_variable(
            variable_id,
            source_filter=source_filter,
            extra_filter=extra_filter,
        )
        return merge_visualization_names(base_names, plugin_names)

    def source_row_for_visualization_pick(variable_id: str, visualization_name: str) -> Dict[str, str]:
        var_id = str(variable_id or "").strip()
        vis = str(visualization_name or "").strip()
        if not var_id or not vis:
            return {}
        if is_plugin_visualization(vis):
            return {}

        query = {
            "variable_id": var_id,
            "variable_type": {"$in": list(VISUALIZATION_PAYLOAD_VARIABLE_TYPES)},
            "visualization_name": vis,
        }
        qf = active_query_filter()
        if qf:
            query = and_filter(qf, query)
        proj = {
            "_id": 1,
            "variable_id": 1,
            "source_dataset": 1,
            "schema_file_group": 1,
            "schema_mode": 1,
            "producer": 1,
            "casename": 1,
            "file": 1,
        }

        try:
            doc = collection.find_one(query, proj)
        except Exception:
            doc = None
        if not doc:
            return {}

        row = {
            "variable_id": str(doc.get("variable_id", "") or var_id),
            "source_dataset": str(doc.get("source_dataset", "") or ""),
            "schema_file_group": str(doc.get("schema_file_group", "") or ""),
            "schema_mode": str(doc.get("schema_mode", "") or ""),
            "producer": str(doc.get("producer", "") or ""),
            "casename": str(doc.get("casename", "") or ""),
            "file": str(doc.get("file", "") or ""),
        }
        row["_key"] = source_key_for_fields(row)
        return row

    def active_source_filter_for_variable(variable_id: str) -> Dict[str, str]:
        if str(state.detailsSelectedVarId or "") != str(variable_id or ""):
            return {}

        selected = set(state.selectedSourceKeys or [])
        row = next((r for r in all_source_rows() if str(r.get("_key", "")) in selected), None)
        return source_filter_from_row(row) if row else {}

    def empty_grid_cell() -> Dict[str, Any]:
        return {
            "variable_id": "",
            "variable_name": "",
            "display_title": "",
            "visualization_name": "",
            "selected_visualization": "",
            "visualization_options": [],
            "_source_key": "",
            "_source_keys": [],
            "_source_fields_list": [],
            "source_dataset": "",
            "producer": "",
            "casename": "",
            "file": "",
            "src": "",
            "media_type": "",
            "fps": 0,
            "frame_count": 0,
            "frame_indices": [],
            "frame_sources": [],
            "time_values": [],
            "time_mode": "timestep",
            "plot": {},
            "plot_settings": {},
            "plugin_id": "",
            "plugin_label": "",
            "plugin_options": {},
            "plugin_options_schema": [],
            "scalar_field_settings": {},
            "scalar_field_colorbar_min": "",
            "scalar_field_colorbar_max": "",
            "grid_row": 1,
            "grid_col": 1,
            "row_span": 1,
            "col_span": 1,
            "grid_hidden": False,
            "status": "empty",
            "note": "",
        }

    def plot_series_key(item: Dict[str, Any], index: int) -> str:
        key = str(item.get("source_key", "") or "").strip()
        if key:
            return key
        label = str(item.get("source_label", "") or "").strip()
        return label or f"series:{index}"

    def plot_series_label(item: Dict[str, Any], index: int) -> str:
        label = str(item.get("source_label", "") or "").strip()
        if label:
            return label
        key = str(item.get("source_key", "") or "").strip()
        return key or f"Series {index + 1}"

    def color_number(value: Any) -> Optional[float]:
        try:
            number = float(str(value).strip())
        except Exception:
            return None
        return number if math.isfinite(number) else None

    def format_color_number(value: float) -> str:
        if abs(value - round(value)) < 1e-9:
            return str(int(round(value)))
        return f"{value:.6g}"

    def clean_rgb_component(value: Any) -> Optional[str]:
        text = str(value or "").strip()
        if not text:
            return None
        if text.endswith("%"):
            number = color_number(text[:-1])
            if number is None or number < 0 or number > 100:
                return None
            return f"{format_color_number(number)}%"
        number = color_number(text)
        if number is None or number < 0 or number > 255:
            return None
        return format_color_number(number)

    def clean_hsl_hue(value: Any) -> Optional[str]:
        text = str(value or "").strip().lower()
        if text.endswith("deg"):
            text = text[:-3].strip()
        number = color_number(text)
        if number is None:
            return None
        return format_color_number(number)

    def clean_hsl_percent(value: Any) -> Optional[str]:
        text = str(value or "").strip()
        if not text:
            return None
        if text.endswith("%"):
            number = color_number(text[:-1])
        else:
            number = color_number(text)
            if number is not None and 0 <= number <= 1:
                number *= 100
        if number is None or number < 0 or number > 100:
            return None
        return f"{format_color_number(number)}%"

    def split_css_color_args(value: str) -> List[str]:
        if "/" in value:
            return []
        if "," in value:
            parts = [part.strip() for part in value.split(",")]
        else:
            parts = value.split()
        return [part for part in parts if part]

    def has_non_opaque_alpha(value: Dict[str, Any]) -> bool:
        if "a" not in value:
            return False
        alpha = color_number(value.get("a"))
        return alpha is not None and abs(alpha - 1.0) > 1e-9

    def clean_plot_color(value: Any, fallback: str) -> str:
        if isinstance(value, dict):
            if has_non_opaque_alpha(value):
                return fallback
            if {"r", "g", "b"}.issubset(value.keys()):
                r = clean_rgb_component(value.get("r"))
                g = clean_rgb_component(value.get("g"))
                b = clean_rgb_component(value.get("b"))
                return f"rgb({r}, {g}, {b})" if r and g and b else fallback
            if {"h", "s", "l"}.issubset(value.keys()):
                h = clean_hsl_hue(value.get("h"))
                s = clean_hsl_percent(value.get("s"))
                lightness = clean_hsl_percent(value.get("l"))
                return f"hsl({h}, {s}, {lightness})" if h and s and lightness else fallback
            for field in ("hex", "css", "value"):
                if field in value:
                    return clean_plot_color(value.get(field), fallback)
            return fallback

        color = str(value or "").strip()
        if re.fullmatch(r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?", color):
            return color

        rgb_match = re.fullmatch(r"rgb\((.*)\)", color, flags=re.IGNORECASE)
        if rgb_match:
            parts = split_css_color_args(rgb_match.group(1))
            if len(parts) == 3:
                r = clean_rgb_component(parts[0])
                g = clean_rgb_component(parts[1])
                b = clean_rgb_component(parts[2])
                if r and g and b:
                    return f"rgb({r}, {g}, {b})"

        hsl_match = re.fullmatch(r"hsl\((.*)\)", color, flags=re.IGNORECASE)
        if hsl_match:
            parts = split_css_color_args(hsl_match.group(1))
            if len(parts) == 3:
                h = clean_hsl_hue(parts[0])
                s = clean_hsl_percent(parts[1])
                lightness = clean_hsl_percent(parts[2])
                if h and s and lightness:
                    return f"hsl({h}, {s}, {lightness})"

        return fallback

    def clean_line_style(value: Any, fallback: str = "solid") -> str:
        style = str(value or "").strip().lower().replace("_", "-")
        return style if style in {"solid", "dash", "dot", "dash-dot"} else fallback

    def to_bool(value: Any, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            text = value.strip().lower()
            if text in {"true", "1", "yes", "on"}:
                return True
            if text in {"false", "0", "no", "off"}:
                return False
        return default

    def finite_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        try:
            number = float(text)
        except Exception:
            return None
        return number if math.isfinite(number) else None

    def plot_series(tile: Dict[str, Any]) -> List[Dict[str, Any]]:
        plot = dict(tile.get("plot", {}) or {})
        raw_series = plot.get("series", []) or []
        return [dict(item or {}) for item in raw_series if isinstance(item, dict)]

    def assign_plot_series_keys(tile: Dict[str, Any], source_keys: List[str]) -> Dict[str, Any]:
        plot = dict(tile.get("plot", {}) or {})
        raw_series = plot.get("series", []) or []
        series: List[Dict[str, Any]] = []
        for i, raw_item in enumerate(raw_series):
            item = dict(raw_item or {})
            if not str(item.get("source_key", "") or "").strip() and i < len(source_keys):
                item["source_key"] = str(source_keys[i] or "")
            series.append(item)
        plot["series"] = series
        tile["plot"] = plot
        return tile

    def source_name_for_row(row: Dict[str, Any]) -> str:
        source_label = str(row.get("source_label", "") or "")
        if source_label:
            return source_label
        schema_file_group = str(row.get("schema_file_group", "") or "")
        if schema_file_group:
            return schema_file_group
        source_dataset = str(row.get("source_dataset", "") or "")
        if source_dataset:
            return source_dataset
        parts = [
            str(row.get("producer", "") or ""),
            str(row.get("casename", "") or ""),
            str(row.get("file", "") or ""),
        ]
        return "/".join(part for part in parts if part)

    def source_row_from_summary_source(source: Dict[str, Any], variable_id: str) -> Dict[str, Any]:
        row = {
            "source_dataset": str(source.get("source_dataset", "") or ""),
            "source_label": str(source.get("source_label", "") or ""),
            "schema_name": str(source.get("schema_name", "") or ""),
            "schema_file_group": str(source.get("schema_file_group", "") or ""),
            "schema_role": str(source.get("schema_role", "") or ""),
            "schema_mode": str(source.get("schema_mode", "") or ""),
            "num_timesteps": int(source.get("num_timesteps", 1) or 1),
            "files": list(source.get("files", []) or []),
            "source_datasets": list(source.get("source_datasets", []) or []),
            "variable_id": str(source.get("variable_id", "") or variable_id or ""),
            "variable_name": str(source.get("variable_name", "") or ""),
            "variable_type": str(source.get("variable_type", "variable") or "variable"),
            "variable_path": str(source.get("variable_path", "") or ""),
            "producer": str(source.get("producer", "") or ""),
            "casename": str(source.get("casename", "") or ""),
            "file": str(source.get("file", "") or ""),
            "visualization_name": str(source.get("visualization_name", "") or ""),
            "visualization_kind": str(source.get("visualization_kind", "") or ""),
            "visualization_source_dataset": str(source.get("visualization_source_dataset", "") or ""),
            "association_source": str(source.get("association_source", "") or ""),
            "campaign_path": str(source.get("campaign_path", "") or ""),
            "variable_location": str(source.get("variable_location", "") or ""),
            "frame_index": source.get("frame_index", None),
            "min": fmt(source.get("min", None)),
            "max": fmt(source.get("max", None)),
            "min_value": source.get("min", None),
            "max_value": source.get("max", None),
        }
        row["_key"] = source_key_for_fields(row)
        row["sourceName"] = source_name_for_row(row)
        return row

    def first_query_source_row_for_variable(variable_id: str, preferred_vis: str = "") -> Dict[str, Any]:
        var_id = str(variable_id or "").strip()
        vis = str(preferred_vis or "").strip()
        if not var_id:
            return {}

        if vis and vis != GENERATED_SCALAR_PLOT_VIS:
            row = source_row_for_visualization_pick(var_id, vis)
            if row:
                return row

        summary = db.variable_min_max_summary(var_id, extra_filter=active_query_filter())
        for source in summary.get("sources", []) or []:
            row = source_row_from_summary_source(dict(source or {}), var_id)
            if source_filter_from_row(row):
                return row
        return {}

    def source_filter_number(value: Any) -> Optional[float]:
        if value is None:
            return None
        text = str(value).strip()
        if not text or text.lower() == "n/a":
            return None
        try:
            numeric = float(text)
        except Exception:
            return None
        return numeric if math.isfinite(numeric) else None

    def source_filter_values(row: Dict[str, Any]) -> Dict[str, Any]:
        variable_id = str(row.get("variable_id", "") or "")
        variable_name = str(row.get("variable_name", "") or "").strip()
        if not variable_name and variable_id:
            variable_name = variable_id.strip("/").rsplit("/", 1)[-1]
        source_dataset = str(row.get("source_dataset", "") or "")
        return {
            "variable_id": variable_id,
            "variable_name": variable_name,
            "variable_type": str(row.get("variable_type", "") or "variable"),
            "source_dataset": source_dataset,
            "source_label": str(row.get("source_label", "") or ""),
            "sourceName": str(row.get("sourceName", "") or ""),
            "schema_name": str(row.get("schema_name", "") or ""),
            "schema_file_group": str(row.get("schema_file_group", "") or ""),
            "schema_role": str(row.get("schema_role", "") or ""),
            "schema_mode": str(row.get("schema_mode", "") or ""),
            "num_timesteps": source_filter_number(row.get("num_timesteps", None)),
            "producer": str(row.get("producer", "") or ""),
            "casename": str(row.get("casename", "") or ""),
            "file": str(row.get("file", "") or ""),
            "visualization_name": str(row.get("visualization_name", "") or ""),
            "visualization_kind": str(row.get("visualization_kind", "") or ""),
            "visualization_source_dataset": str(row.get("visualization_source_dataset", "") or source_dataset),
            "association_source": str(row.get("association_source", "") or ""),
            "variable_path": str(row.get("variable_path", "") or ""),
            "campaign_path": str(row.get("campaign_path", "") or ""),
            "variable_location": str(row.get("variable_location", "") or ""),
            "frame_index": source_filter_number(row.get("frame_index", None)),
            "min": source_filter_number(row.get("min_value", row.get("min", None))),
            "max": source_filter_number(row.get("max_value", row.get("max", None))),
        }

    def valid_title_extrema(fmin: Any, fmax: Any) -> Tuple[Optional[float], Optional[float]]:
        min_value = finite_float(fmin)
        max_value = finite_float(fmax)
        if min_value is None or max_value is None or min_value > max_value:
            return None, None
        return min_value, max_value

    def source_extrema_for_title(variable_id: str, source_filter: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
        var_id = str(variable_id or "").strip()
        if not var_id or not source_filter:
            return None, None

        qf = active_query_filter()
        extra_filter = and_filter(qf, source_filter) if qf else source_filter
        summary = db.variable_min_max_summary(var_id, extra_filter=extra_filter)
        return valid_title_extrema(
            summary.get("global_min", None),
            summary.get("global_max", None),
        )

    def update_2d_display_title(cell: Dict[str, Any], variable_id: str, label: str) -> None:
        media_type = str(cell.get("media_type", "") or "")
        if media_type not in {"image", "image_sequence", "video"}:
            cell["display_title"] = str(label or "")
            cell["scalar_field_colorbar_min"] = ""
            cell["scalar_field_colorbar_max"] = ""
            return

        title_min: Optional[float] = None
        title_max: Optional[float] = None
        if is_scalar_field_cell(cell):
            fmin, fmax = source_extrema_for_title(
                variable_id,
                source_filter_from_cell(cell),
            )
            if fmin is None or fmax is None:
                fmin, fmax = valid_title_extrema(cell.get("min", None), cell.get("max", None))
            title_min, title_max = fmin, fmax
        else:
            fmin, fmax = valid_title_extrema(cell.get("min", None), cell.get("max", None))
            if fmin is None or fmax is None:
                fmin, fmax = source_extrema_for_title(
                    variable_id,
                    source_filter_from_cell(cell),
                )

        if fmin is None or fmax is None:
            cell["display_title"] = str(label or "")
        else:
            cell["display_title"] = f"{label} [{fmt(fmin)}, {fmt(fmax)}]"

        cell["scalar_field_colorbar_min"] = ""
        cell["scalar_field_colorbar_max"] = ""
        if is_scalar_field_cell(cell):
            settings = normalize_scalar_field_settings(cell.get("scalar_field_settings", {}))
            if not bool(settings.get("range_auto", True)):
                bar_min = finite_float(settings.get("min", None))
                bar_max = finite_float(settings.get("max", None))
            else:
                bar_min, bar_max = title_min, title_max
            if bar_min is not None and bar_max is not None:
                cell["scalar_field_colorbar_min"] = fmt(bar_min)
                cell["scalar_field_colorbar_max"] = fmt(bar_max)

    def source_sort_key(row: Dict[str, Any], field: str, selected_keys: set):
        if field == "show":
            key = str(row.get("_key", ""))
            # Ascending puts the active source first.
            return (0 if key in selected_keys else 1, key)

        value = row.get(field, "")
        if field in ("min", "max"):
            numeric = source_filter_number(row.get(f"{field}_value", value))
            if numeric is not None:
                return ("__num__", numeric)

        if value is None:
            return ("__str__", "")
        return ("__str__", str(value).lower())

    def sorted_source_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        field = str(state.sourceSortField or "")
        if not field:
            return list(rows)
        selected_keys = set(state.selectedSourceKeys or [])
        asc = bool(state.sourceSortAsc)
        return sorted(
            rows,
            key=lambda row: source_sort_key(row, field, selected_keys),
            reverse=(not asc),
        )

    def apply_source_filter_and_sort():
        rows = all_source_rows()
        expr = str(state.sourceFilterText or "").strip()
        if expr:
            try:
                row_filter, source_filters = python_query_to_filters(expr)
                source_restriction = {}
                if source_filters:
                    source_summary = db.source_restriction_summary(source_filters)
                    source_restriction = dict(source_summary.get("filter", {}) or {})
                matched_rows = []
                for row in rows:
                    values = source_filter_values(row)
                    if mongo_filter_matches(row_filter, values) and mongo_filter_matches(source_restriction, values):
                        matched_rows.append(row)
                rows = matched_rows
                state.sourceFilterError = ""
            except Exception as e:
                state.sourceFilterError = f"{type(e).__name__}: {e}"
                rows = all_source_rows()
        else:
            state.sourceFilterError = ""

        state.sourceRows = sorted_source_rows(rows)
        update_selected_source_label()

    def normalize_plot_settings(
        tile: Dict[str, Any],
        raw_settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        raw = dict(raw_settings or {})
        raw_colors = raw.get("series_colors", {})
        raw_colors = raw_colors if isinstance(raw_colors, dict) else {}
        raw_styles = raw.get("series_styles", {})
        raw_styles = raw_styles if isinstance(raw_styles, dict) else {}
        palette = (
            "#1565c0",
            "#c62828",
            "#2e7d32",
            "#ef6c00",
            "#6a1b9a",
            "#00838f",
            "#ad1457",
            "#5d4037",
        )

        series_colors: Dict[str, str] = {}
        series_styles: Dict[str, Dict[str, str]] = {}
        for i, item in enumerate(plot_series(tile)):
            key = plot_series_key(item, i)
            raw_style = raw_styles.get(key, {})
            raw_style = raw_style if isinstance(raw_style, dict) else {}
            fallback = str(item.get("color", "") or "") or palette[i % len(palette)]
            color = clean_plot_color(raw_style.get("color", raw_colors.get(key, "")), fallback)
            line_style = clean_line_style(raw_style.get("line_style", "solid"))
            series_colors[key] = color
            series_styles[key] = {
                "color": color,
                "line_style": line_style,
            }

        def scale_value(key: str) -> str:
            value = str(raw.get(key, "linear") or "linear").strip().lower()
            return value if value in {"linear", "log"} else "linear"

        try:
            line_width = float(raw.get("line_width", 2.5))
        except Exception:
            line_width = 2.5
        if not math.isfinite(line_width):
            line_width = 2.5
        line_width = max(0.5, min(8.0, line_width))

        return {
            "x_auto": to_bool(raw.get("x_auto", True), True),
            "x_min": finite_float(raw.get("x_min", None)),
            "x_max": finite_float(raw.get("x_max", None)),
            "x_scale": scale_value("x_scale"),
            "y_auto": to_bool(raw.get("y_auto", True), True),
            "y_min": finite_float(raw.get("y_min", None)),
            "y_max": finite_float(raw.get("y_max", None)),
            "y_scale": scale_value("y_scale"),
            "series_colors": series_colors,
            "series_styles": series_styles,
            "line_width": line_width,
            "show_grid": to_bool(raw.get("show_grid", True), True),
            "show_cursor": to_bool(raw.get("show_cursor", True), True),
            "background_color": clean_plot_color(raw.get("background_color", ""), "#ffffff"),
            "grid_color": clean_plot_color(raw.get("grid_color", ""), "#e8e8e8"),
            "cursor_color": clean_plot_color(raw.get("cursor_color", ""), "#111111"),
        }

    def existing_plot_settings(existing_cell: Dict[str, Any], variable_id: str) -> Dict[str, Any]:
        if not isinstance(existing_cell, dict):
            return {}
        existing_var = str(existing_cell.get("variable_id", "") or existing_cell.get("variable_name", "") or "")
        if existing_var != str(variable_id or ""):
            return {}
        if str(existing_cell.get("media_type", "") or "") != "plot1d":
            return {}
        settings = existing_cell.get("plot_settings", {})
        return dict(settings or {}) if isinstance(settings, dict) else {}

    def plot_series_rows_for_tile(tile: Dict[str, Any], settings: Dict[str, Any]) -> List[Dict[str, str]]:
        colors = settings.get("series_colors", {})
        colors = colors if isinstance(colors, dict) else {}
        styles = settings.get("series_styles", {})
        styles = styles if isinstance(styles, dict) else {}
        rows: List[Dict[str, str]] = []
        for i, item in enumerate(plot_series(tile)):
            key = plot_series_key(item, i)
            style = styles.get(key, {})
            style = style if isinstance(style, dict) else {}
            rows.append(
                {
                    "key": key,
                    "label": plot_series_label(item, i),
                    "color": clean_plot_color(style.get("color", colors.get(key, "")), str(item.get("color", "") or "#1565c0")),
                    "line_style": clean_line_style(style.get("line_style", "solid")),
                }
            )
        return rows

    def is_generated_plot1d_cell(cell: Dict[str, Any]) -> bool:
        if str(cell.get("media_type", "") or "") != "plot1d":
            return False
        selected_vis = str(cell.get("selected_visualization", "") or cell.get("visualization_name", "") or "").strip()
        visualization_name = str(cell.get("visualization_name", "") or selected_vis).strip()
        return selected_vis == GENERATED_SCALAR_PLOT_VIS or visualization_name == GENERATED_SCALAR_PLOT_VIS

    def axis_has_positive_data(tile: Dict[str, Any], axis: str) -> bool:
        field = "x" if axis == "x" else "y"
        for item in plot_series(tile):
            values = item.get(field, []) or []
            for raw_value in values:
                value = finite_float(raw_value)
                if value is not None and value > 0:
                    return True
        return False

    def settings_value_text(value: Any) -> str:
        number = finite_float(value)
        return "" if number is None else f"{number:.12g}"

    def scalar_colormap(value: Any) -> str:
        name = str(value or "viridis").strip().lower()
        return name if name in SCALAR_FIELD_COLORMAPS else "viridis"

    def scalar_colormap_gradient(value: Any) -> str:
        name = scalar_colormap(value)
        return SCALAR_FIELD_COLORMAP_CSS_GRADIENTS.get(
            name,
            SCALAR_FIELD_COLORMAP_CSS_GRADIENTS.get("viridis", ""),
        )

    def normalize_scalar_field_settings(raw_settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        raw = dict(raw_settings or {})
        range_mode = str(raw.get("range_mode", "") or "").strip().lower()
        range_auto = raw.get("range_auto", None)
        if range_auto is None:
            range_auto = range_mode != "manual"
        range_auto = to_bool(range_auto, True)
        min_value = finite_float(raw.get("min", None))
        max_value = finite_float(raw.get("max", None))
        if range_auto or min_value is None or max_value is None or min_value >= max_value:
            min_value = None
            max_value = None
            range_auto = True

        return {
            "colormap": scalar_colormap(raw.get("colormap", "viridis")),
            "colorbar_gradient": scalar_colormap_gradient(raw.get("colormap", "viridis")),
            "range_auto": range_auto,
            "range_mode": "auto" if range_auto else "manual",
            "min": min_value,
            "max": max_value,
            "show_colorbar": to_bool(raw.get("show_colorbar", False), False),
            "show_axes": to_bool(raw.get("show_axes", False), False),
        }

    def is_scalar_field_cell(cell: Dict[str, Any]) -> bool:
        variable_type = str(cell.get("variable_type", "") or "").strip()
        payload_type = str(cell.get("payload_type", "") or "").strip().upper()
        item_type = str(cell.get("visualization_item_type", "") or "").strip().upper()
        return (
            variable_type == SCALAR_FIELD_VARIABLE_TYPE
            or payload_type == "SCALAR_FIELD"
            or item_type == "SCALAR_FIELD"
        )

    def existing_scalar_field_settings(existing_cell: Optional[Dict[str, Any]], variable_id: str) -> Dict[str, Any]:
        if not isinstance(existing_cell, dict):
            return normalize_scalar_field_settings()
        existing_var = str(existing_cell.get("variable_id", "") or existing_cell.get("variable_name", "") or "")
        if existing_var != str(variable_id or ""):
            return normalize_scalar_field_settings()
        return normalize_scalar_field_settings(existing_cell.get("scalar_field_settings", {}))

    def load_scalar_field_settings_dialog(idx: int, reset: bool = False) -> None:
        cells = normalize_grid_cells(state.gridCells)
        if not is_valid_grid_index(idx):
            return
        cell = dict(cells[idx] or {})
        if not is_scalar_field_cell(cell):
            return

        raw_settings = {} if reset else dict(cell.get("scalar_field_settings", {}) or {})
        settings = normalize_scalar_field_settings(raw_settings)
        state.scalarFieldSettingsCellIndex = idx
        state.scalarFieldSettingsTitle = str(cell.get("variable_name", "") or f"Cell {idx + 1}")
        state.scalarFieldSettingsStatus = ""
        state.scalarFieldSettingsStatusIsError = False
        state.scalarFieldSettingsColormap = str(settings.get("colormap", "viridis") or "viridis")
        state.scalarFieldSettingsRangeAuto = bool(settings.get("range_auto", True))
        state.scalarFieldSettingsMin = settings_value_text(settings.get("min", None))
        state.scalarFieldSettingsMax = settings_value_text(settings.get("max", None))
        state.scalarFieldSettingsShowColorbar = bool(settings.get("show_colorbar", False))
        state.scalarFieldSettingsShowAxes = bool(settings.get("show_axes", False))
        state.showScalarFieldSettingsModal = True

    def load_plot_settings_dialog(idx: int, reset: bool = False) -> None:
        cells = normalize_grid_cells(state.gridCells)
        if not is_valid_grid_index(idx):
            return
        cell = dict(cells[idx] or {})
        if str(cell.get("media_type", "") or "") != "plot1d":
            return

        raw_settings = {} if reset else dict(cell.get("plot_settings", {}) or {})
        settings = normalize_plot_settings(cell, raw_settings)
        state.plotSettingsCellIndex = idx
        state.plotSettingsTitle = str(cell.get("variable_name", "") or f"Cell {idx + 1}")
        state.plotSettingsStatus = ""
        state.plotSettingsCanPluginOptions = is_plugin_visualization(
            str(cell.get("selected_visualization", "") or cell.get("visualization_name", "") or "")
        )
        state.plotSettingsXAuto = bool(settings.get("x_auto", True))
        state.plotSettingsXMin = settings_value_text(settings.get("x_min", None))
        state.plotSettingsXMax = settings_value_text(settings.get("x_max", None))
        state.plotSettingsXScale = str(settings.get("x_scale", "linear") or "linear")
        state.plotSettingsYAuto = bool(settings.get("y_auto", True))
        state.plotSettingsYMin = settings_value_text(settings.get("y_min", None))
        state.plotSettingsYMax = settings_value_text(settings.get("y_max", None))
        state.plotSettingsYScale = str(settings.get("y_scale", "linear") or "linear")
        state.plotSettingsLineWidth = float(settings.get("line_width", 2.5) or 2.5)
        state.plotSettingsShowGrid = bool(settings.get("show_grid", True))
        state.plotSettingsShowCursor = bool(settings.get("show_cursor", True))
        state.plotSettingsBackgroundColor = clean_plot_color(settings.get("background_color", ""), "#ffffff")
        state.plotSettingsGridColor = clean_plot_color(settings.get("grid_color", ""), "#e8e8e8")
        state.plotSettingsCursorColor = clean_plot_color(settings.get("cursor_color", ""), "#111111")
        state.plotSettingsSeriesRows = plot_series_rows_for_tile(cell, settings)
        state.showPlotSettingsModal = True

    def plugin_option_rows(schema: List[Dict[str, Any]], values: Dict[str, Any]) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for item in schema or []:
            spec = dict(item or {})
            key = str(spec.get("key", "") or "").strip()
            if not key:
                continue
            option_type = str(spec.get("type", "text") or "text")
            value = values.get(key, spec.get("default", False if option_type == "bool" else ""))
            if option_type == "bool":
                value = bool(value)
            else:
                value = str(value or "")
            rows.append(
                {
                    "key": key,
                    "label": str(spec.get("label", "") or key),
                    "type": option_type,
                    "value": value,
                    "choices": list(spec.get("choices", []) or []),
                }
            )
        return rows

    def plugin_options_from_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        options: Dict[str, Any] = {}
        for raw_row in rows or []:
            row = dict(raw_row or {})
            key = str(row.get("key", "") or "").strip()
            if not key:
                continue
            if str(row.get("type", "") or "") == "bool":
                options[key] = bool(row.get("value", False))
            else:
                options[key] = str(row.get("value", "") or "").strip()
        return options

    def load_plugin_options_dialog(idx: int, reset: bool = False) -> None:
        cells = normalize_grid_cells(state.gridCells)
        if not is_valid_grid_index(idx):
            return
        cell = dict(cells[idx] or {})
        selected_vis = str(cell.get("selected_visualization", "") or cell.get("visualization_name", "") or "")
        if not is_plugin_visualization(selected_vis):
            return

        schema = list(cell.get("plugin_options_schema", []) or [])
        options = {} if reset else dict(cell.get("plugin_options", {}) or {})
        options = normalize_plugin_options(schema, options)
        state.pluginOptionsCellIndex = idx
        state.pluginOptionsTitle = str(cell.get("display_title", "") or cell.get("variable_name", "") or f"Cell {idx + 1}")
        state.pluginOptionsStatus = ""
        state.pluginOptionsRows = plugin_option_rows(schema, options)
        state.showPluginOptionsModal = True

    def clear_context_menu_state() -> None:
        state.contextMenuVisible = False
        state.contextMenuKind = ""
        state.contextMenuItem = ""
        state.contextMenuItemLabel = ""
        state.contextMenuCellIndex = -1
        state.contextMenuCellHasVariable = False
        state.contextMenuCellCanAddSource = False
        state.contextMenuCellCanPlotSettings = False
        state.contextMenuCellCanScalarFieldSettings = False
        state.contextMenuCellCanResetView = False
        state.contextMenuCellVisualizationOptions = []
        state.contextMenuCellSelectedVisualization = ""
        state.contextMenuCellSourcePlugins = []

    def show_help(title: str) -> None:
        state.helpModalTitle = title
        if str(title or "") in {"Query Help", "Source Filter Help"}:
            scope_note = (
                "Query applies globally to the variable list, source lists, grid cells, and generated plots."
                if str(title or "") == "Query Help"
                else "Source Filter applies only to source rows that already passed the active Query."
            )
            state.helpModalText = f"""Use Python-like expressions to filter variables and sources.

{scope_note}

Basic fields:
  var                 variable name, e.g. 'U', 'V', 'valid'
  id                  variable id
  type                variable type, e.g. 'variable', 'image', 'scalarField'
  source or dataset   source dataset path
  producer            run/producer name
  casename            case name
  file                file name
  visualization_name  visualization name
  min, max            variable/source min and max values
  frame_index         visualization frame index

Operators:
  ==  !=  >  >=  <  <=
  in, not in
  and, or, not

Functions:
  contains(field, 'text')   substring match on a text field
                            literal and case-sensitive

Examples:
  var == 'U'
  var in ['U', 'V']
  var == 'U' and min > 0.32
  contains(producer, 'F0.03968')
  contains(source, 'output.bp')
  visualization_name == 'U_heatmap_yz'
  producer == 'Du0.0979_Dv0.0526_F0.01634_k0.0502'

Source restrictions:
  Use source(...) to restrict to runs/sources that match another query.

  source(var == 'valid' and min == 1)

In Query, this keeps only sources/runs where valid == 1 while still allowing you to select U, V, and other variables.
In Source Filter, this keeps only visible source rows from those sources/runs.

Multiple source(...) clauses are intersected:

  source(var == 'valid' and min == 1) and source(var == 'U' and min > 0.32)

This keeps sources/runs where valid == 1 and U.min > 0.32.

Notes:
  var == 'valid' and min == 1 filters directly to the valid variable rows.
  source(var == 'valid' and min == 1) filters sources/runs for all variables.
  source(...) is supported as a top-level clause combined with and.
"""
        else:
            state.helpModalText = "TODO"
        state.showHelpModal = True

    def clamp_int(value, default: int, minimum: int, maximum: int) -> int:
        try:
            ivalue = int(value)
        except Exception:
            ivalue = default
        return max(minimum, min(maximum, ivalue))

    GRID_LAYOUT_FIELDS = ("grid_row", "grid_col", "row_span", "col_span", "grid_hidden")

    def normalize_grid_layout_mode() -> str:
        mode = str(getattr(state, "gridLayoutMode", "uniform") or "uniform").strip().lower()
        state.gridLayoutMode = "spanning" if mode == "spanning" else "uniform"
        return state.gridLayoutMode

    def grid_dimensions() -> Tuple[int, int]:
        rows = clamp_int(getattr(state, "gridRows", 3), 3, GRID_MIN_ROWS, GRID_MAX_ROWS)
        cols = clamp_int(getattr(state, "gridCols", 3), 3, GRID_MIN_COLS, GRID_MAX_COLS)
        state.gridRows = rows
        state.gridCols = cols
        state.gridMinRows = GRID_MIN_ROWS
        state.gridMinCols = GRID_MIN_COLS
        state.gridMaxRows = GRID_MAX_ROWS
        state.gridMaxCols = GRID_MAX_COLS
        return rows, cols

    def default_grid_geometry(index: int, cols: int) -> Dict[str, Any]:
        safe_cols = max(1, int(cols or 1))
        return {
            "grid_row": (index // safe_cols) + 1,
            "grid_col": (index % safe_cols) + 1,
            "row_span": 1,
            "col_span": 1,
            "grid_hidden": False,
        }

    def merge_grid_geometry(cell: Dict[str, Any], index: int, rows: int, cols: int) -> Dict[str, Any]:
        base = dict(cell or {})
        defaults = default_grid_geometry(index, cols)
        row = clamp_int(base.get("grid_row", defaults["grid_row"]), defaults["grid_row"], 1, rows)
        col = clamp_int(base.get("grid_col", defaults["grid_col"]), defaults["grid_col"], 1, cols)
        base["grid_row"] = row
        base["grid_col"] = col
        base["row_span"] = clamp_int(base.get("row_span", 1), 1, 1, max(1, rows - row + 1))
        base["col_span"] = clamp_int(base.get("col_span", 1), 1, 1, max(1, cols - col + 1))
        base["grid_hidden"] = bool(base.get("grid_hidden", False))
        return base

    def cell_has_content(cell: Dict[str, Any]) -> bool:
        if str(cell.get("variable_id", "") or cell.get("variable_name", "") or "").strip():
            return True
        if str(cell.get("src", "") or cell.get("media_type", "") or "").strip():
            return True
        if cell.get("plot"):
            return True
        return str(cell.get("status", "") or "") not in {"", "empty"}

    def preserve_grid_geometry(cell: Dict[str, Any], existing: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(cell or {})
        if isinstance(existing, dict):
            for field in GRID_LAYOUT_FIELDS:
                if field in existing:
                    merged[field] = existing[field]
        return merged

    def assign_cell(cells: List[Dict[str, Any]], idx: int, cell: Dict[str, Any]) -> None:
        cells[idx] = preserve_grid_geometry(cell, cells[idx] if 0 <= idx < len(cells) else {})

    def empty_grid_cell_like(existing: Dict[str, Any]) -> Dict[str, Any]:
        return preserve_grid_geometry(empty_grid_cell(), existing)

    def area_slots(row: int, col: int, row_span: int, col_span: int, cols: int) -> List[int]:
        return [
            (r - 1) * cols + (c - 1)
            for r in range(row, row + row_span)
            for c in range(col, col + col_span)
        ]

    def empty_cell_at(index: int, cols: int, hidden: bool = False) -> Dict[str, Any]:
        cell = empty_grid_cell()
        cell.update(default_grid_geometry(index, cols))
        cell["grid_hidden"] = bool(hidden)
        return cell

    def rebuild_spanning_cells(raw_cells: List[Dict[str, Any]], rows: int, cols: int) -> List[Dict[str, Any]]:
        count = rows * cols
        merged: List[Dict[str, Any]] = []
        for i, item in enumerate(raw_cells or []):
            base = empty_grid_cell()
            if isinstance(item, dict):
                base.update(item)
            merged.append(merge_grid_geometry(base, i, rows, cols))
        while len(merged) < count:
            merged.append(empty_cell_at(len(merged), cols))

        cells = [empty_cell_at(i, cols) for i in range(count)]
        occupied: set[int] = set()

        def first_open_area(row_span: int, col_span: int) -> Optional[Tuple[int, int]]:
            for row in range(1, rows - row_span + 2):
                for col in range(1, cols - col_span + 2):
                    slots = area_slots(row, col, row_span, col_span, cols)
                    if all(slot not in occupied for slot in slots):
                        return row, col
            return None

        def place(cell: Dict[str, Any], row: int, col: int, row_span: int, col_span: int) -> None:
            anchor = (row - 1) * cols + (col - 1)
            item = dict(cell or {})
            item["grid_row"] = row
            item["grid_col"] = col
            item["row_span"] = row_span
            item["col_span"] = col_span
            item["grid_hidden"] = False
            cells[anchor] = item
            for slot in area_slots(row, col, row_span, col_span, cols):
                occupied.add(slot)
                if slot != anchor:
                    cells[slot] = empty_cell_at(slot, cols, hidden=True)

        anchors = [
            cell
            for cell in merged
            if not bool(cell.get("grid_hidden", False))
            and (
                cell_has_content(cell)
                or int(cell.get("row_span", 1) or 1) > 1
                or int(cell.get("col_span", 1) or 1) > 1
            )
        ]

        for cell in anchors:
            row = clamp_int(cell.get("grid_row", 1), 1, 1, rows)
            col = clamp_int(cell.get("grid_col", 1), 1, 1, cols)
            row_span = clamp_int(cell.get("row_span", 1), 1, 1, max(1, rows - row + 1))
            col_span = clamp_int(cell.get("col_span", 1), 1, 1, max(1, cols - col + 1))
            slots = area_slots(row, col, row_span, col_span, cols)
            if any(slot in occupied for slot in slots):
                open_area = first_open_area(row_span, col_span)
                if open_area is None:
                    continue
                row, col = open_area
            place(cell, row, col, row_span, col_span)

        return cells

    def normalize_grid_sizing() -> None:
        mode = str(getattr(state, "gridSizingMode", "static") or "static").strip().lower()
        state.gridSizingMode = "fit" if mode == "fit" else "static"
        state.gridMinCellSize = clamp_int(getattr(state, "gridMinCellSize", 80), 80, 40, 1000)
        state.gridMaxCellSize = clamp_int(getattr(state, "gridMaxCellSize", 5000), 5000, state.gridMinCellSize, 10000)
        state.gridCellSize = clamp_int(
            getattr(state, "gridCellSize", 300),
            300,
            state.gridMinCellSize,
            state.gridMaxCellSize,
        )
        state.gridMaxFitMinCellSize = clamp_int(
            getattr(state, "gridMaxFitMinCellSize", 5000),
            5000,
            state.gridMinCellSize,
            10000,
        )
        state.gridFitMinCellSize = clamp_int(
            getattr(state, "gridFitMinCellSize", 180),
            180,
            state.gridMinCellSize,
            state.gridMaxFitMinCellSize,
        )

    def size_values(raw_sizes) -> List[Any]:
        if isinstance(raw_sizes, str):
            return [part.strip() for part in raw_sizes.replace(";", ",").split(",")]
        if isinstance(raw_sizes, (list, tuple)):
            return list(raw_sizes)
        return []

    def normalize_size_list(raw_sizes, count: int, default: int, minimum: int, maximum: int) -> List[int]:
        values = size_values(raw_sizes)
        sizes: List[int] = []
        for idx in range(count):
            raw = values[idx] if idx < len(values) else default
            sizes.append(clamp_int(raw, default, minimum, maximum))
        return sizes

    def normalize_weight_list(raw_weights, count: int, default: float = 1.0) -> List[float]:
        values = size_values(raw_weights)
        weights: List[float] = []
        for idx in range(count):
            raw = values[idx] if idx < len(values) else default
            value = finite_float(raw)
            if value is None or value <= 0:
                value = default
            value = max(GRID_MIN_TRACK_WEIGHT, min(GRID_MAX_TRACK_WEIGHT, float(value)))
            weights.append(round(value, 6))
        return weights

    def grid_template_from_sizes(sizes: List[int]) -> str:
        return " ".join(f"{int(size)}px" for size in sizes)

    def grid_fit_template_from_weights(weights: List[float], min_size: int) -> str:
        safe_min = max(1, int(min_size))
        return " ".join(f"minmax({safe_min}px, {float(weight):.6g}fr)" for weight in weights)

    def publish_grid_track_templates() -> None:
        state.gridColumnTemplate = grid_template_from_sizes(list(state.gridColumnSizes or []))
        state.gridRowTemplate = grid_template_from_sizes(list(state.gridRowSizes or []))
        state.gridFitColumnTemplate = grid_fit_template_from_weights(
            list(state.gridColumnWeights or []),
            int(state.gridFitMinCellSize),
        )
        state.gridFitRowTemplate = grid_fit_template_from_weights(
            list(state.gridRowWeights or []),
            int(state.gridFitMinCellSize) + GRID_HEADER_HEIGHT,
        )

    def normalize_grid_track_sizes(rows: Optional[int] = None, cols: Optional[int] = None) -> None:
        normalize_grid_sizing()
        if rows is None or cols is None:
            rows, cols = grid_dimensions()

        col_default = int(state.gridCellSize)
        row_default = int(state.gridCellSize) + GRID_HEADER_HEIGHT
        state.gridColumnSizes = normalize_size_list(
            getattr(state, "gridColumnSizes", []),
            int(cols),
            col_default,
            int(state.gridMinCellSize),
            int(state.gridMaxCellSize),
        )
        state.gridRowSizes = normalize_size_list(
            getattr(state, "gridRowSizes", []),
            int(rows),
            row_default,
            int(state.gridMinCellSize) + GRID_HEADER_HEIGHT,
            int(state.gridMaxCellSize) + GRID_HEADER_HEIGHT,
        )
        state.gridColumnWeights = normalize_weight_list(
            getattr(state, "gridColumnWeights", []),
            int(cols),
        )
        state.gridRowWeights = normalize_weight_list(
            getattr(state, "gridRowWeights", []),
            int(rows),
        )
        publish_grid_track_templates()

    def reset_grid_track_sizes() -> None:
        normalize_grid_sizing()
        rows, cols = grid_dimensions()
        state.gridColumnSizes = [int(state.gridCellSize) for _ in range(cols)]
        state.gridRowSizes = [int(state.gridCellSize) + GRID_HEADER_HEIGHT for _ in range(rows)]
        state.gridColumnWeights = [1.0 for _ in range(cols)]
        state.gridRowWeights = [1.0 for _ in range(rows)]
        publish_grid_track_templates()

    def drop_grid_track(axis: str, index: int) -> None:
        if axis == "row":
            sizes = list(getattr(state, "gridRowSizes", []) or [])
            if 0 <= index < len(sizes):
                del sizes[index]
            state.gridRowSizes = sizes
            weights = list(getattr(state, "gridRowWeights", []) or [])
            if 0 <= index < len(weights):
                del weights[index]
            state.gridRowWeights = weights
        elif axis == "column":
            sizes = list(getattr(state, "gridColumnSizes", []) or [])
            if 0 <= index < len(sizes):
                del sizes[index]
            state.gridColumnSizes = sizes
            weights = list(getattr(state, "gridColumnWeights", []) or [])
            if 0 <= index < len(weights):
                del weights[index]
            state.gridColumnWeights = weights

    def grid_cell_count() -> int:
        rows, cols = grid_dimensions()
        return rows * cols

    def is_valid_grid_index(idx: int) -> bool:
        return 0 <= idx < grid_cell_count()

    def active_grid_index(cell_count: int = -1) -> int:
        try:
            idx = int(state.activeGridCell)
        except Exception:
            return -1
        if cell_count < 0:
            cell_count = grid_cell_count()
        return idx if 0 <= idx < cell_count else -1

    def is_selectable_grid_cell(cells: List[Dict[str, Any]], idx: int) -> bool:
        if idx < 0 or idx >= len(cells):
            return False
        cell = dict(cells[idx] or {})
        if bool(cell.get("grid_hidden", False)):
            return False
        return bool(str(cell.get("variable_id", "") or cell.get("variable_name", "") or "").strip())

    def normalize_grid_selection(
        raw_indices: Optional[List[Any]] = None,
        cells: Optional[List[Dict[str, Any]]] = None,
    ) -> List[int]:
        if cells is None:
            cells = normalize_grid_cells(state.gridCells)
        items = raw_indices if raw_indices is not None else list(state.selectedGridCellIndices or [])
        selected: List[int] = []
        for raw_idx in items or []:
            try:
                idx = int(raw_idx)
            except Exception:
                continue
            if idx in selected or not is_selectable_grid_cell(cells, idx):
                continue
            selected.append(idx)
        return selected

    def set_grid_selection(indices: List[int], active: Optional[int] = None) -> None:
        cells = normalize_grid_cells(state.gridCells)
        selected = normalize_grid_selection(indices, cells)
        publish_grid_selection(selected)
        if active is not None and is_valid_grid_index(active):
            state.activeGridCell = int(active)

    def clear_timeline_driver_if_cell(idx: int) -> None:
        try:
            if int(state.timelineDriverCell) == int(idx):
                state.timelineDriverCell = -1
        except Exception:
            state.timelineDriverCell = -1

    def cell_has_timeline_samples(cell: Dict[str, Any]) -> bool:
        time_values = cell.get("time_values", [])
        if isinstance(time_values, list) and any(finite_float(value) is not None for value in time_values):
            return True

        plot = cell.get("plot", {})
        if not isinstance(plot, dict):
            return False
        x_label = str(plot.get("x_label", "") or "").strip().lower()
        if x_label not in {"time", "physical time"}:
            return False
        for item in plot.get("series", []) or []:
            if not isinstance(item, dict):
                continue
            x_values = item.get("x", [])
            if isinstance(x_values, list) and any(finite_float(value) is not None for value in x_values):
                return True
        return False

    def publish_grid_selection(selected: List[int]) -> None:
        state.selectedGridCellIndices = selected
        state.selectedGridCellMap = {str(idx): True for idx in selected}

    def source_dialog_targets_for_anchor(idx: int, cells: Optional[List[Dict[str, Any]]] = None) -> List[int]:
        if cells is None:
            cells = normalize_grid_cells(state.gridCells)
        if not is_selectable_grid_cell(cells, idx):
            return []
        selected = normalize_grid_selection(cells=cells)
        if idx in selected and len(selected) > 1:
            return selected
        return [idx]

    def source_row_for_variable(row: Dict[str, Any], variable_id: str) -> Dict[str, str]:
        target = {
            "variable_id": str(variable_id or ""),
            "source_dataset": str(row.get("source_dataset", "") or ""),
            "schema_file_group": str(row.get("schema_file_group", "") or ""),
            "schema_mode": str(row.get("schema_mode", "") or ""),
            "producer": str(row.get("producer", "") or ""),
            "casename": str(row.get("casename", "") or ""),
            "file": str(row.get("file", "") or ""),
        }
        target["_key"] = source_key_for_fields(target)
        return target

    def normalize_grid_cells(raw_cells, rows=None, cols=None) -> List[Dict[str, Any]]:
        if rows is None or cols is None:
            rows, cols = grid_dimensions()

        count = rows * cols
        mode = normalize_grid_layout_mode()
        raw_items = list(raw_cells or [])
        items = raw_items if mode == "spanning" else raw_items[:count]
        cells: List[Dict[str, Any]] = []
        for i, item in enumerate(items):
            base = empty_grid_cell()
            if isinstance(item, dict):
                base.update(item)
            if mode == "uniform":
                base.update(default_grid_geometry(i, cols))
            else:
                base = merge_grid_geometry(base, i, rows, cols)
            cells.append(base)
        while len(cells) < count:
            cells.append(empty_cell_at(len(cells), cols))
        if mode == "spanning":
            return rebuild_spanning_cells(cells, rows, cols)
        return cells

    def set_grid_layout(rows: int, cols: int, cells: List[Dict[str, Any]], active: int) -> None:
        rows = clamp_int(rows, 3, GRID_MIN_ROWS, GRID_MAX_ROWS)
        cols = clamp_int(cols, 3, GRID_MIN_COLS, GRID_MAX_COLS)
        cells = normalize_grid_cells(cells, rows, cols)
        state.gridRows = rows
        state.gridCols = cols
        normalize_grid_track_sizes(rows, cols)
        state.gridCells = normalize_grid_cells(cells)
        state.activeGridCell = active if 0 <= active < rows * cols else -1
        try:
            if int(state.timelineDriverCell) >= rows * cols:
                state.timelineDriverCell = -1
        except Exception:
            state.timelineDriverCell = -1
        publish_grid_selection(normalize_grid_selection(cells=list(state.gridCells or [])))
        clear_context_menu_state()

    @ctrl.add("set_grid_layout_mode")
    def set_grid_layout_mode(mode: str, **_):
        state.gridLayoutMode = "spanning" if str(mode or "").strip().lower() == "spanning" else "uniform"
        rows, cols = grid_dimensions()
        active = active_grid_index(rows * cols)
        state.gridCells = normalize_grid_cells(state.gridCells, rows, cols)
        state.activeGridCell = active if 0 <= active < rows * cols else -1
        publish_grid_selection(normalize_grid_selection(cells=list(state.gridCells or [])))

    @ctrl.add("set_grid_cell_size")
    def set_grid_cell_size(size: int, **_):
        normalize_grid_sizing()
        state.gridCellSize = clamp_int(size, 300, state.gridMinCellSize, state.gridMaxCellSize)
        reset_grid_track_sizes()

    @ctrl.add("set_grid_fit_min_cell_size")
    def set_grid_fit_min_cell_size(size: int, **_):
        normalize_grid_sizing()
        state.gridFitMinCellSize = clamp_int(
            size,
            180,
            state.gridMinCellSize,
            state.gridMaxFitMinCellSize,
        )
        normalize_grid_track_sizes()

    @ctrl.add("set_grid_sizing_mode")
    def set_grid_sizing_mode(mode: str, **_):
        state.gridSizingMode = "fit" if str(mode or "").strip().lower() == "fit" else "static"
        normalize_grid_sizing()
        normalize_grid_track_sizes()

    @ctrl.add("reset_grid_track_sizes")
    def reset_grid_track_sizes_action(**_):
        reset_grid_track_sizes()

    @ctrl.trigger("set_grid_track_sizes_trigger")
    def set_grid_track_sizes_trigger(axis: str, sizes="", **_):
        axis_name = str(axis or "").strip().lower()
        normalize_grid_sizing()
        rows, cols = grid_dimensions()
        if axis_name == "column":
            state.gridColumnSizes = normalize_size_list(
                sizes,
                cols,
                int(state.gridCellSize),
                int(state.gridMinCellSize),
                int(state.gridMaxCellSize),
            )
        elif axis_name == "row":
            state.gridRowSizes = normalize_size_list(
                sizes,
                rows,
                int(state.gridCellSize) + GRID_HEADER_HEIGHT,
                int(state.gridMinCellSize) + GRID_HEADER_HEIGHT,
                int(state.gridMaxCellSize) + GRID_HEADER_HEIGHT,
            )
        else:
            return
        state.gridSizingMode = "static"
        normalize_grid_track_sizes(rows, cols)

    @ctrl.trigger("set_grid_track_weights_trigger")
    def set_grid_track_weights_trigger(axis: str, weights="", **_):
        axis_name = str(axis or "").strip().lower()
        normalize_grid_sizing()
        rows, cols = grid_dimensions()
        if axis_name == "column":
            state.gridColumnWeights = normalize_weight_list(weights, cols)
        elif axis_name == "row":
            state.gridRowWeights = normalize_weight_list(weights, rows)
        else:
            return
        state.gridSizingMode = "fit"
        normalize_grid_track_sizes(rows, cols)

    @ctrl.add("set_grid_layout_size")
    def set_grid_layout_size(rows: int, cols: int, **_):
        old_rows, old_cols = grid_dimensions()
        new_rows = clamp_int(rows, old_rows, GRID_MIN_ROWS, GRID_MAX_ROWS)
        new_cols = clamp_int(cols, old_cols, GRID_MIN_COLS, GRID_MAX_COLS)
        if new_rows == old_rows and new_cols == old_cols:
            return

        if normalize_grid_layout_mode() == "spanning":
            old_cells = normalize_grid_cells(state.gridCells, old_rows, old_cols)
            active = active_grid_index(old_rows * old_cols)
            new_active = -1
            if active >= 0:
                active_cell = old_cells[active]
                row = clamp_int(active_cell.get("grid_row", 1), 1, 1, old_rows)
                col = clamp_int(active_cell.get("grid_col", 1), 1, 1, old_cols)
                if row <= new_rows and col <= new_cols:
                    new_active = (row - 1) * new_cols + (col - 1)
            set_grid_layout(new_rows, new_cols, old_cells, new_active)
            return

        old_cells = normalize_grid_cells(state.gridCells, old_rows, old_cols)
        new_cells: List[Dict[str, Any]] = []
        for row in range(new_rows):
            for col in range(new_cols):
                if row < old_rows and col < old_cols:
                    new_cells.append(old_cells[row * old_cols + col])
                else:
                    new_cells.append(empty_grid_cell())

        active = active_grid_index(old_rows * old_cols)
        new_active = -1
        if active >= 0:
            active_row = active // old_cols
            active_col = active % old_cols
            if active_row < new_rows and active_col < new_cols:
                new_active = active_row * new_cols + active_col

        set_grid_layout(new_rows, new_cols, new_cells, new_active)

    def choose_visualization_default(vis_names: List[str], preferred_vis: str = "") -> str:
        preferred = str(preferred_vis or "").strip()
        if preferred and preferred in vis_names:
            return preferred
        if "heatmap" in vis_names:
            return "heatmap"
        return vis_names[0] if vis_names else ""

    def variable_label(variable_id: str) -> str:
        item_id = str(variable_id or "").strip()
        labels = dict(state.variableLabelsById or {})
        return str(labels.get(item_id, "") or item_id)

    def normalize_scalar_plot_policy() -> str:
        policy = str(state.scalarPlotPolicy or "always").strip().lower()
        if policy not in {"ask", "always", "never"}:
            policy = "always"
        state.scalarPlotPolicy = policy
        return policy

    def clear_pending_scalar_plot() -> None:
        state.showScalarPlotDialog = False
        state.pendingScalarPlotVariableId = ""
        state.pendingScalarPlotCellIndex = -1
        state.pendingScalarPlotSourceFields = {}
        state.pendingScalarPlotSyncSelection = True
        state.scalarPlotDialogMessage = ""
        state.scalarPlotAlwaysForSession = False

    def source_fields_to_filter(variable_id: str, source_fields: Dict[str, Any]) -> Dict[str, Any]:
        cell = dict(source_fields or {})
        cell["variable_id"] = str(variable_id or "")
        return source_filter_from_cell(cell)

    def source_filter_for_assignment(
        variable_id: str,
        source_row: Optional[Dict[str, str]] = None,
        existing_cell: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if source_row:
            return source_filter_from_row(source_row)
        if existing_cell:
            return source_filter_from_cell(existing_cell)
        return active_source_filter_for_variable(variable_id)

    def source_fields_for_assignment(
        variable_id: str,
        source_row: Optional[Dict[str, str]] = None,
        candidate: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if source_row:
            return source_fields_from_row(source_row)
        source_fields = dict((candidate or {}).get("source_fields", {}) or {})
        if source_fields:
            return source_fields
        source_filter = active_source_filter_for_variable(variable_id)
        return {
            "source_dataset": str(source_filter.get("source_dataset", "") or ""),
            "schema_file_group": str(source_filter.get("schema_file_group", "") or ""),
            "schema_mode": str(source_filter.get("schema_mode", "") or ""),
            "producer": str(source_filter.get("producer", "") or ""),
            "casename": str(source_filter.get("casename", "") or ""),
            "file": str(source_filter.get("file", "") or ""),
        }

    def build_plugin_grid_cell(
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
            source_filter = source_filter_from_cell(existing_cell)
        else:
            source_filter = active_source_filter_for_variable(var_id)

        query_filter = active_query_filter()
        candidate = plugin_candidate(
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
        tile = render_plugin_tile(campaign_path, plugin_id, candidate, options=options)
        label = variable_label(var_id)
        source_fields = source_fields_for_assignment(var_id, source_row=source_row, candidate=candidate)
        if existing_cell and not source_fields.get("_source_key"):
            source_fields["_source_key"] = str(existing_cell.get("_source_key", "") or "")
        tile.update({k: v for k, v in source_fields.items() if v})
        source_key = str(source_fields.get("_source_key", "") or "")
        tile["_source_keys"] = [source_key] if source_key else []
        tile["_source_fields_list"] = [source_fields] if source_fields else []
        if str(tile.get("media_type", "") or "") == "plot1d":
            assign_plot_series_keys(tile, [source_key] if source_key else [])
            tile["plot_settings"] = normalize_plot_settings(tile, existing_plot_settings(existing_cell, var_id))
        active_filter = and_filter(query_filter, source_filter) if query_filter and source_filter else (query_filter or source_filter or None)
        base_vis = db.distinct_visualization_names_for_variable(var_id, extra_filter=active_filter)
        plugin_vis_names = supported_plugin_visualizations(meta)
        tile["visualization_options"] = merge_visualization_names(base_vis, plugin_vis_names)
        tile["visualization_name"] = plugin_vis
        tile["selected_visualization"] = plugin_vis
        tile["variable_id"] = var_id
        tile["variable_name"] = label
        tile["plugin_options_schema"] = schema
        tile["plugin_options"] = options
        tile.setdefault("src", "")
        return tile

    def build_grid_cell_for_variable(
        variable_id: str,
        preferred_vis: str = "",
        source_row: Optional[Dict[str, str]] = None,
        existing_cell: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        cell = empty_grid_cell()
        var_id = str(variable_id or "").strip()
        if not var_id:
            return cell
        label = variable_label(var_id)
        scalar_settings = existing_scalar_field_settings(existing_cell, var_id)

        qf = active_query_filter()
        source_fields: Dict[str, str] = {}
        if source_row:
            source_fields = source_fields_from_row(source_row)
            source_filter = source_filter_from_row(source_row)
        elif existing_cell:
            source_fields = {
                "_source_key": str(existing_cell.get("_source_key", "") or ""),
                "source_dataset": str(existing_cell.get("source_dataset", "") or ""),
                "schema_file_group": str(existing_cell.get("schema_file_group", "") or ""),
                "schema_mode": str(existing_cell.get("schema_mode", "") or ""),
                "producer": str(existing_cell.get("producer", "") or ""),
                "casename": str(existing_cell.get("casename", "") or ""),
                "file": str(existing_cell.get("file", "") or ""),
            }
            source_filter = source_filter_from_cell(existing_cell)
        else:
            source_filter = active_source_filter_for_variable(var_id)
        active_filter = and_filter(qf, source_filter) if qf and source_filter else (qf or source_filter or None)
        vis_names = visualization_names_with_plugins(
            var_id,
            source_filter=source_filter,
            extra_filter=active_filter,
        )
        if existing_cell and source_filter and not vis_names:
            fallback_row = first_query_source_row_for_variable(var_id, preferred_vis)
            if fallback_row:
                source_fields = source_fields_from_row(fallback_row)
                source_filter = source_filter_from_row(fallback_row)
                active_filter = and_filter(qf, source_filter) if qf and source_filter else (qf or source_filter or None)
                vis_names = visualization_names_with_plugins(
                    var_id,
                    source_filter=source_filter,
                    extra_filter=active_filter,
                )

        selected_vis = choose_visualization_default(vis_names, preferred_vis)
        if selected_vis and is_plugin_visualization(selected_vis):
            return build_plugin_grid_cell(
                var_id,
                selected_vis,
                source_row=source_row,
                existing_cell=existing_cell,
            )

        cell.update(
            {
                "variable_id": var_id,
                "variable_name": label,
                "visualization_name": selected_vis,
                "selected_visualization": selected_vis,
                "visualization_options": vis_names,
                "status": "no-visualizations",
                "note": "No visualization types for this variable",
            }
        )
        cell.update({k: v for k, v in source_fields.items() if v})

        if selected_vis:
            movie_query = (
                and_filter(active_filter, {"visualization_name": selected_vis})
                if active_filter
                else {"visualization_name": selected_vis}
            )
            one = db.get_first_movie_tiles_for_variable(
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
                if is_scalar_field_cell(cell):
                    cell["scalar_field_settings"] = scalar_settings
            else:
                cell["status"] = "no-frames"
                cell["note"] = f'No movie for "{selected_vis}"'

        if not str(cell.get("_source_key", "") or ""):
            row = source_row_for_cell(cell)
            if row:
                cell.update(source_fields_from_row(row))

        cell["variable_id"] = var_id
        cell["variable_name"] = label
        cell["visualization_name"] = selected_vis
        cell["selected_visualization"] = selected_vis
        cell["visualization_options"] = vis_names
        if is_scalar_field_cell(cell):
            cell["scalar_field_settings"] = scalar_settings
        update_2d_display_title(cell, var_id, label)
        return cell

    def no_visualization_grid_cell(variable_id: str, note: str) -> Dict[str, Any]:
        cell = empty_grid_cell()
        cell["variable_id"] = variable_id
        cell["variable_name"] = variable_label(variable_id)
        cell["status"] = "no-visualizations"
        cell["note"] = note
        return cell

    def set_generated_scalar_plot_cell(
        cell_index: int,
        variable_id: str,
        source_fields: Optional[Dict[str, Any]] = None,
        sync_selection: bool = True,
    ) -> bool:
        try:
            idx = int(cell_index)
        except Exception:
            return False
        if not is_valid_grid_index(idx):
            return False

        source_fields = dict(source_fields or {})
        source_filter = source_fields_to_filter(variable_id, source_fields)
        try:
            tile = db.get_or_create_generated_scalar_plot_tile(
                campaign_path,
                variable_id,
                source_filter=source_filter or None,
                extra_filter=active_query_filter(),
            )
        except Exception as e:
            tile = {}
            state.scalarPlotStatus = f"Scalar plot generation failed: {type(e).__name__}: {e}"

        cells = normalize_grid_cells(state.gridCells)
        prior_settings = existing_plot_settings(cells[idx], variable_id)
        if tile:
            tile.update({k: v for k, v in source_fields.items() if v})
            source_key = str(source_fields.get("_source_key", "") or "")
            assign_plot_series_keys(tile, [source_key] if source_key else [])
            tile["plot_settings"] = normalize_plot_settings(tile, prior_settings)
            tile["visualization_name"] = str(tile.get("visualization_name", "") or GENERATED_SCALAR_PLOT_VIS)
            tile["selected_visualization"] = str(tile.get("selected_visualization", "") or GENERATED_SCALAR_PLOT_VIS)
            tile["visualization_options"] = [GENERATED_SCALAR_PLOT_VIS]
            assign_cell(cells, idx, tile)
            state.scalarPlotStatus = ""
        else:
            assign_cell(
                cells,
                idx,
                no_visualization_grid_cell(
                    variable_id,
                    "Could not generate scalar plot for this source",
                ),
            )

        state.gridCells = normalize_grid_cells(cells)
        state.activeGridCell = idx
        if sync_selection:
            state.selectedVar = variable_id
            state.draggedVar = variable_id
        return bool(tile)

    def set_generated_scalar_plot_sources_cell(
        cell_index: int,
        variable_id: str,
        source_rows: List[Dict[str, str]],
        sync_selection: bool = True,
    ) -> bool:
        try:
            idx = int(cell_index)
        except Exception:
            return False
        if not is_valid_grid_index(idx):
            return False

        rows = [row for row in source_rows if row]
        if not rows:
            return False

        source_fields_list = [source_fields_from_row(row) for row in rows]
        source_filters = [source_filter_from_row(row) for row in rows]
        source_keys = [
            str(fields.get("_source_key", "") or "")
            for fields in source_fields_list
            if str(fields.get("_source_key", "") or "")
        ]
        try:
            tile = db.get_generated_scalar_plot_tile_for_sources(
                campaign_path,
                variable_id,
                source_filters=source_filters,
                extra_filter=active_query_filter(),
            )
        except Exception as e:
            tile = {}
            state.scalarPlotStatus = f"Scalar plot generation failed: {type(e).__name__}: {e}"

        cells = normalize_grid_cells(state.gridCells)
        prior_settings = existing_plot_settings(cells[idx], variable_id)
        if tile:
            first_fields = source_fields_list[0]
            tile.update({k: v for k, v in first_fields.items() if v and k != "_source_key"})
            tile["_source_key"] = source_keys[0] if source_keys else str(first_fields.get("_source_key", "") or "")
            tile["_source_keys"] = source_keys
            tile["_source_fields_list"] = source_fields_list
            assign_plot_series_keys(tile, source_keys)
            tile["plot_settings"] = normalize_plot_settings(tile, prior_settings)
            tile["visualization_name"] = GENERATED_SCALAR_PLOT_VIS
            tile["selected_visualization"] = GENERATED_SCALAR_PLOT_VIS
            tile["visualization_options"] = [GENERATED_SCALAR_PLOT_VIS]
            assign_cell(cells, idx, tile)
            state.scalarPlotStatus = ""
        else:
            assign_cell(
                cells,
                idx,
                no_visualization_grid_cell(
                    variable_id,
                    "Could not generate scalar plot for the selected sources",
                ),
            )

        state.gridCells = cells
        state.activeGridCell = idx
        if sync_selection:
            state.selectedVar = variable_id
            state.draggedVar = variable_id
        return bool(tile)

    def generated_scalar_plot_cell_for_source_rows(
        variable_id: str,
        source_rows: List[Dict[str, Any]],
        existing_cell: Dict[str, Any],
        allow_multi_sources: bool,
    ) -> Dict[str, Any]:
        var_id = str(variable_id or "").strip()
        rows = [source_row_for_variable(row, var_id) for row in source_rows if row]
        if not var_id or not rows:
            raise ValueError("No source selected")

        prior_settings = existing_plot_settings(existing_cell, var_id)
        if allow_multi_sources and len(rows) > 1:
            source_fields_list = [source_fields_from_row(row) for row in rows]
            source_filters = [source_filter_from_row(row) for row in rows]
            source_keys = [
                str(fields.get("_source_key", "") or "")
                for fields in source_fields_list
                if str(fields.get("_source_key", "") or "")
            ]
            tile = db.get_generated_scalar_plot_tile_for_sources(
                campaign_path,
                var_id,
                source_filters=source_filters,
                extra_filter=active_query_filter(),
            )
            if not tile:
                raise ValueError("Could not generate scalar plot for the selected sources")

            first_fields = source_fields_list[0]
            tile.update({k: v for k, v in first_fields.items() if v and k != "_source_key"})
            tile["_source_key"] = source_keys[0] if source_keys else str(first_fields.get("_source_key", "") or "")
            tile["_source_keys"] = source_keys
            tile["_source_fields_list"] = source_fields_list
            assign_plot_series_keys(tile, source_keys)
        else:
            source_fields = source_fields_from_row(rows[0])
            source_filter = source_fields_to_filter(var_id, source_fields)
            tile = db.get_or_create_generated_scalar_plot_tile(
                campaign_path,
                var_id,
                source_filter=source_filter or None,
                extra_filter=active_query_filter(),
            )
            if not tile:
                raise ValueError("Could not generate scalar plot for this source")

            tile.update({k: v for k, v in source_fields.items() if v})
            source_key = str(source_fields.get("_source_key", "") or "")
            tile["_source_keys"] = [source_key] if source_key else []
            tile["_source_fields_list"] = [source_fields] if source_fields else []
            assign_plot_series_keys(tile, [source_key] if source_key else [])

        tile["plot_settings"] = normalize_plot_settings(tile, prior_settings)
        tile["visualization_name"] = GENERATED_SCALAR_PLOT_VIS
        tile["selected_visualization"] = GENERATED_SCALAR_PLOT_VIS
        tile["visualization_options"] = [GENERATED_SCALAR_PLOT_VIS]
        return tile

    def build_cell_for_source_rows(
        variable_id: str,
        existing_cell: Dict[str, Any],
        source_rows: List[Dict[str, Any]],
        allow_multi_sources: bool,
    ) -> Dict[str, Any]:
        var_id = str(variable_id or "").strip()
        if not var_id:
            raise ValueError("Cell has no variable")
        if not source_rows:
            raise ValueError("No source selected")

        existing = dict(existing_cell or {})
        if is_generated_plot1d_cell(existing):
            return generated_scalar_plot_cell_for_source_rows(
                var_id,
                source_rows,
                existing,
                allow_multi_sources,
            )

        target_row = source_row_for_variable(source_rows[0], var_id)
        selected_vis = str(existing.get("selected_visualization", "") or existing.get("visualization_name", "") or "")
        new_cell = build_grid_cell_for_variable(
            var_id,
            preferred_vis=selected_vis,
            source_row=target_row,
            existing_cell=existing,
        )
        status = str(new_cell.get("status", "") or "")
        if status in {"error", "no-visualizations"}:
            note = str(new_cell.get("note", "") or "No visualization for this source")
            raise ValueError(note)
        return new_cell

    def source_dialog_target_indices() -> List[int]:
        cells = normalize_grid_cells(state.gridCells)
        raw_targets = list(state.sourceDialogTargetCellIndices or [])
        if not raw_targets:
            try:
                raw_targets = [int(state.sourceDialogCellIndex)]
            except Exception:
                raw_targets = []
        return normalize_grid_selection(raw_targets, cells)

    def source_dialog_multi_source_allowed(targets: List[int], cells: List[Dict[str, Any]]) -> bool:
        return bool(targets) and all(is_generated_plot1d_cell(cells[idx]) for idx in targets)

    def apply_source_rows_to_targets(
        target_indices: List[int],
        selected_source_keys: List[str],
        allow_multi_sources: bool,
    ) -> Tuple[int, List[str]]:
        source_rows = source_rows_for_keys(selected_source_keys)
        if not source_rows:
            return 0, ["No sources selected"]

        cells = normalize_grid_cells(state.gridCells)
        targets = normalize_grid_selection(target_indices, cells)
        if not targets:
            return 0, ["No plot cells selected"]

        updated = list(cells)
        failures: List[str] = []
        applied = 0
        for idx in targets:
            existing = dict(updated[idx] or {})
            var_id = str(existing.get("variable_id", "") or existing.get("variable_name", "") or "").strip()
            if not var_id:
                failures.append(f"Cell {idx + 1}: no variable")
                continue
            try:
                new_cell = build_cell_for_source_rows(
                    var_id,
                    existing,
                    source_rows,
                    allow_multi_sources and is_generated_plot1d_cell(existing),
                )
            except Exception as e:
                failures.append(f"Cell {idx + 1}: {e}")
                continue
            assign_cell(updated, idx, new_cell)
            applied += 1

        if applied:
            state.gridCells = normalize_grid_cells(updated)
            anchor = targets[0]
            state.activeGridCell = anchor
            publish_grid_selection(normalize_grid_selection(targets, list(state.gridCells or [])))
        return applied, failures

    def open_source_dialog_for_cell(cell_index: int, prefer_multi: bool = False) -> None:
        if not is_valid_grid_index(cell_index):
            return
        cells = normalize_grid_cells(state.gridCells)
        targets = source_dialog_targets_for_anchor(cell_index, cells)
        if not targets:
            return

        cell = dict(cells[cell_index] or {})
        var = str(cell.get("variable_id", "") or cell.get("variable_name", "") or "").strip()
        if not var:
            return

        multi_allowed = source_dialog_multi_source_allowed(targets, cells)
        source_keys = source_keys_from_cell(cell)
        preferred_key = source_keys[0] if source_keys else str(cell.get("_source_key", "") or "")

        state.activeGridCell = cell_index
        publish_grid_selection(targets)
        state.sourceDialogTargetCellIndices = targets
        state.sourceDialogCellIndex = cell_index
        state.sourceDialogMode = "add" if (prefer_multi or len(targets) > 1) and multi_allowed else "single"
        if len(targets) > 1:
            state.sourceDialogTitle = f"Sources: {variable_label(var)} - applying to {len(targets)} cells"
        else:
            state.sourceDialogTitle = f"{'Add Source' if str(state.sourceDialogMode or '') == 'add' else 'Sources'}: {variable_label(var)}"
        state.sourceDialogStatus = ""
        state.sourceDialogStatusIsError = False
        state.selectedVar = var
        state.draggedVar = var

        if str(state.sourceDialogMode or "") == "add":
            update_selected_var_panels(var, preferred_source_keys=source_keys)
        else:
            update_selected_var_panels(var, preferred_source_key=preferred_key)
        state.sourceDialogInitialSelectedSourceKeys = normalize_source_keys(state.selectedSourceKeys or source_keys)
        state.showSourcesModal = True

    def maybe_handle_generated_scalar_plot(
        variable_id: str,
        cell_index: int,
        source_row: Optional[Dict[str, str]] = None,
        sync_selection: bool = True,
    ) -> bool:
        source_filter = source_filter_for_assignment(variable_id, source_row=source_row)
        qf = active_query_filter()
        active_filter = and_filter(qf, source_filter) if qf and source_filter else (qf or source_filter or None)
        if visualization_names_with_plugins(variable_id, source_filter=source_filter, extra_filter=active_filter):
            return False

        candidate = db.scalar_plot_candidate(
            variable_id,
            source_filter=source_filter or None,
            extra_filter=qf,
        )
        if not candidate:
            return False

        source_fields = source_fields_for_assignment(variable_id, source_row=source_row, candidate=candidate)
        source_label = str(candidate.get("source_label", "") or "").strip()
        label = variable_label(variable_id)
        policy = normalize_scalar_plot_policy()
        state.activeGridCell = cell_index
        state.selectedVar = variable_id
        state.draggedVar = variable_id

        if policy == "never":
            cells = normalize_grid_cells(state.gridCells)
            note = "No saved visualization; scalar plot generation is disabled"
            assign_cell(cells, cell_index, no_visualization_grid_cell(variable_id, note))
            state.gridCells = normalize_grid_cells(cells)
            state.scalarPlotStatus = note
            return True

        if policy == "always":
            set_generated_scalar_plot_cell(
                cell_index,
                variable_id,
                source_fields=source_fields,
                sync_selection=sync_selection,
            )
            return True

        state.pendingScalarPlotVariableId = variable_id
        state.pendingScalarPlotCellIndex = cell_index
        state.pendingScalarPlotSourceFields = source_fields
        state.pendingScalarPlotSyncSelection = bool(sync_selection)
        state.scalarPlotDialogMessage = (
            f'"{label}" has no saved visualization'
            + (f" for {source_label}" if source_label else "")
            + ". Generate a scalar plot from the raw campaign data?"
        )
        state.scalarPlotAlwaysForSession = False
        state.showScalarPlotDialog = True
        state.scalarPlotStatus = ""
        return True

    def refresh_grid_cells():
        cells = normalize_grid_cells(state.gridCells)
        updated: List[Dict[str, Any]] = []

        for c in cells:
            var_id = str(c.get("variable_id", "") or c.get("variable_name", "") or "").strip()
            if not var_id:
                updated.append(empty_grid_cell_like(c))
                continue

            if is_plugin_visualization(str(c.get("visualization_name", "") or c.get("selected_visualization", "") or "")):
                selected_vis = str(c.get("selected_visualization", "") or c.get("visualization_name", "") or "")
                try:
                    tile = build_plugin_grid_cell(
                        var_id,
                        selected_vis,
                        existing_cell=c,
                        plugin_options=dict(c.get("plugin_options", {}) or {}),
                    )
                    updated.append(preserve_grid_geometry(tile, c))
                except Exception as e:
                    err_cell = no_visualization_grid_cell(var_id, f"{type(e).__name__}: {e}")
                    updated.append(preserve_grid_geometry(err_cell, c))
                continue

            if str(c.get("visualization_name", "") or "") == GENERATED_SCALAR_PLOT_VIS:
                source_keys = source_keys_from_cell(c)
                source_fields_list = source_fields_list_from_cell(c)
                try:
                    if len(source_fields_list) > 1:
                        valid_source_fields_list: List[Dict[str, Any]] = []
                        valid_source_keys: List[str] = []
                        for fields in source_fields_list:
                            source_filter = source_fields_to_filter(var_id, fields)
                            if db.scalar_plot_candidate(
                                var_id,
                                source_filter=source_filter or None,
                                extra_filter=active_query_filter(),
                            ):
                                valid_source_fields_list.append(fields)
                                source_key = str(fields.get("_source_key", "") or "")
                                if source_key:
                                    valid_source_keys.append(source_key)
                        source_fields_list = valid_source_fields_list
                        source_keys = valid_source_keys
                        if not source_fields_list:
                            raise ValueError("Could not regenerate scalar plot for selected sources")
                        source_filters = [
                            source_fields_to_filter(var_id, fields)
                            for fields in source_fields_list
                        ]
                        tile = db.get_generated_scalar_plot_tile_for_sources(
                            campaign_path,
                            var_id,
                            source_filters=source_filters,
                            extra_filter=active_query_filter(),
                        )
                        if not tile:
                            raise ValueError("Could not regenerate scalar plot for selected sources")
                        first_fields = source_fields_list[0]
                        tile.update({k: v for k, v in first_fields.items() if v and k != "_source_key"})
                        tile["_source_key"] = source_keys[0] if source_keys else str(first_fields.get("_source_key", "") or "")
                        tile["_source_keys"] = source_keys
                        tile["_source_fields_list"] = source_fields_list
                    else:
                        source_fields = source_fields_list[0] if source_fields_list else {}
                        tile = db.get_or_create_generated_scalar_plot_tile(
                            campaign_path,
                            var_id,
                            source_filter=source_fields_to_filter(var_id, source_fields) or None,
                            extra_filter=active_query_filter(),
                        )
                        if not tile:
                            raise ValueError("Could not regenerate scalar plot for source")
                        tile.update({k: v for k, v in source_fields.items() if v})
                    tile["visualization_name"] = GENERATED_SCALAR_PLOT_VIS
                    tile["selected_visualization"] = GENERATED_SCALAR_PLOT_VIS
                    tile["visualization_options"] = [GENERATED_SCALAR_PLOT_VIS]
                    assign_plot_series_keys(tile, source_keys)
                    tile["plot_settings"] = normalize_plot_settings(tile, existing_plot_settings(c, var_id))
                    updated.append(preserve_grid_geometry(tile, c))
                except Exception as e:
                    fallback_row = first_query_source_row_for_variable(var_id, GENERATED_SCALAR_PLOT_VIS)
                    try:
                        if not fallback_row:
                            raise e
                        source_fields = source_fields_from_row(fallback_row)
                        source_key = str(source_fields.get("_source_key", "") or "")
                        tile = db.get_or_create_generated_scalar_plot_tile(
                            campaign_path,
                            var_id,
                            source_filter=source_fields_to_filter(var_id, source_fields) or None,
                            extra_filter=active_query_filter(),
                        )
                        if not tile:
                            raise e
                        tile.update({k: v for k, v in source_fields.items() if v})
                        tile["visualization_name"] = GENERATED_SCALAR_PLOT_VIS
                        tile["selected_visualization"] = GENERATED_SCALAR_PLOT_VIS
                        tile["visualization_options"] = [GENERATED_SCALAR_PLOT_VIS]
                        tile["_source_keys"] = [source_key] if source_key else []
                        tile["_source_fields_list"] = [source_fields] if source_fields else []
                        assign_plot_series_keys(tile, [source_key] if source_key else [])
                        tile["plot_settings"] = normalize_plot_settings(tile, existing_plot_settings(c, var_id))
                        updated.append(preserve_grid_geometry(tile, c))
                    except Exception as fallback_e:
                        err_cell = no_visualization_grid_cell(var_id, f"{type(fallback_e).__name__}: {fallback_e}")
                        updated.append(preserve_grid_geometry(err_cell, c))
                continue

            preferred_vis = str(c.get("selected_visualization", "") or "")
            try:
                updated.append(
                    preserve_grid_geometry(
                        build_grid_cell_for_variable(var_id, preferred_vis=preferred_vis, existing_cell=c),
                        c,
                    )
                )
            except Exception as e:
                err_cell = empty_grid_cell()
                err_cell["variable_id"] = var_id
                err_cell["variable_name"] = variable_label(var_id)
                err_cell["status"] = "error"
                err_cell["note"] = f"{type(e).__name__}: {e}"
                updated.append(preserve_grid_geometry(err_cell, c))

        state.gridCells = normalize_grid_cells(updated)

        try:
            idx = int(state.activeGridCell)
        except Exception:
            idx = -1
        state.activeGridCell = idx if is_valid_grid_index(idx) else -1

    @ctrl.add("sort_sources")
    def sort_sources(field: str, toggle: bool = True, **_):
        if not field:
            return

        if state.sourceSortField == field:
            if toggle:
                state.sourceSortAsc = not bool(state.sourceSortAsc)
        else:
            state.sourceSortField = field
            state.sourceSortAsc = True

        state.sourceRows = sorted_source_rows(list(state.sourceRows or []))

    def refresh_after_variable_catalog_change():
        refresh_variable_list()
        if state.selectedVar and state.selectedVar not in (state.variableNames or []):
            state.selectedVar = ""
            clear_right_panes(state)
        else:
            update_selected_var_panels(state.selectedVar)
        refresh_grid_cells()

    def update_selected_var_panels(
        variable_id: str,
        preferred_source_key: str = "",
        preferred_source_keys: Optional[List[str]] = None,
    ):
        var_id = str(variable_id or "").strip()
        if not var_id:
            clear_right_panes(state)
            return

        label = variable_label(var_id)
        previous_var = state.detailsSelectedVarId
        previous_tile_map = (
            dict(state.tileVisualizationBySource or {})
            if previous_var == var_id
            else {}
        )
        qf = active_query_filter()
        summary = db.variable_min_max_summary(var_id, extra_filter=qf)

        state.dbOk = db.ok
        state.dbStatus = (
            f'Connected • Selected variable: "{label}" • QueryView: {state.queryViewLabel}'
            if db.ok
            else f'DB error • "{label}" • {db.last_error}'
        )

        state.detailsSelectedVar = label
        state.detailsSelectedVarId = var_id
        state.detailsNumSources = int(summary.get("num_sources", 0))

        state.detailsGlobalMin = fmt(summary.get("global_min", None))
        state.detailsGlobalMax = fmt(summary.get("global_max", None))
        state.detailsMeanMin = fmt(summary.get("mean_min", None))
        state.detailsMeanMax = fmt(summary.get("mean_max", None))
        state.detailsMedianMin = fmt(summary.get("median_min", None))
        state.detailsMedianMax = fmt(summary.get("median_max", None))

        rows = summary.get("sources", []) or []
        source_rows_all: List[Dict[str, Any]] = []
        for r in rows:
            source_rows_all.append(source_row_from_summary_source(dict(r or {}), var_id))

        state.sourceRowsAll = source_rows_all
        apply_source_filter_and_sort()

        all_keys = source_row_keys()
        allow_multi_sources = str(state.sourceDialogMode or "single") == "add"
        preferred_keys = [key for key in normalize_source_keys(preferred_source_keys or []) if key in all_keys]
        preferred_key = str(preferred_source_key or "")
        if preferred_keys:
            state.selectedSourceKeys = preferred_keys if allow_multi_sources else preferred_keys[:1]
        elif preferred_key and preferred_key in all_keys:
            state.selectedSourceKeys = [preferred_key]
        elif previous_var != var_id:
            state.selectedSourceKeys = [all_keys[0]] if all_keys else []
        else:
            selected = set(state.selectedSourceKeys or [])
            selected_keys = [k for k in all_keys if k in selected]
            if allow_multi_sources:
                state.selectedSourceKeys = selected_keys or ([all_keys[0]] if all_keys else [])
            else:
                state.selectedSourceKeys = selected_keys[:1] or ([all_keys[0]] if all_keys else [])
        update_selected_source_label()

        try:
            if all_keys and not state.selectedSourceKeys:
                state.movieTiles = []
                state.movieDetailsOpen = {}
                state.tileVisualizationBySource = {}
                state.movieStatus = "No sources selected"
                return

            selected_rows = source_rows_for_keys(normalize_source_keys(state.selectedSourceKeys or []))

            tiles: List[Dict[str, Any]] = []
            new_tile_map: Dict[str, str] = {}

            for row in selected_rows:
                source_key = str(row.get("_key", ""))
                source_filter = source_filter_from_row(row)
                source_query = and_filter(qf, source_filter) if qf else source_filter

                vis_names = db.distinct_visualization_names_for_variable(
                    var_id,
                    extra_filter=source_query,
                )
                selected_vis = choose_visualization_default(vis_names, previous_tile_map.get(source_key, ""))
                if selected_vis:
                    new_tile_map[source_key] = selected_vis

                tile: Dict[str, Any] = {
                    "variable_id": var_id,
                    "variable_name": label,
                    "visualization_name": selected_vis,
                    "source_dataset": row.get("source_dataset", ""),
                    "producer": row.get("producer", ""),
                    "casename": row.get("casename", ""),
                    "file": row.get("file", ""),
                    "src": "",
                    "media_type": "video",
                    "fps": 0,
                    "frame_count": 0,
                    "frame_indices": [],
                    "frame_sources": [],
                    "time_values": [],
                    "time_mode": "timestep",
                    "status": "no-visualizations",
                    "note": "No visualization types for this source",
                }

                if selected_vis:
                    movie_query = and_filter(source_query, {"visualization_name": selected_vis})
                    one = db.get_first_movie_tiles_for_variable(
                        var_id,
                        extra_filter=movie_query,
                        limit=1,
                        limit_frames=MAX_MOVIE_FRAMES,
                        fps=MOVIE_FPS,
                    )
                    if one:
                        tile = one[0]
                        tile.update({k: v for k, v in source_fields_from_row(row).items() if v})
                    else:
                        tile["status"] = "no-frames"
                        tile["note"] = f'No movie for "{selected_vis}"'

                tile["_source_key"] = source_key
                tile["variable_id"] = var_id
                tile["variable_name"] = label
                tile["visualization_options"] = vis_names
                tile["selected_visualization"] = selected_vis
                tiles.append(tile)

            state.tileVisualizationBySource = new_tile_map
            state.movieTiles = tiles
            state.movieDetailsOpen = {}
            state.movieStatus = ""
            if state.movieTiles:
                with_media = sum(1 for t in state.movieTiles if t.get("src"))
                state.movieStatus = f"{with_media}/{len(state.movieTiles)} sources with media"
        except Exception as e:
            state.movieTiles = []
            state.movieDetailsOpen = {}
            state.tileVisualizationBySource = {}
            state.movieStatus = f"Movie query/build failed: {type(e).__name__}: {e}"

    @ctrl.add("pick_var")
    def pick_var(var_name: str, **_):
        picked = str(var_name or "")
        if str(state.selectedVar or "") == picked:
            state.selectedVar = ""
            state.draggedVar = ""
        else:
            state.selectedVar = picked
            state.draggedVar = picked

    @ctrl.add("select_var")
    def select_var(var_name: str, button=0, **_):
        try:
            if int(button) == 2:
                return
        except Exception:
            pass

        picked = str(var_name or "")
        if not picked:
            return
        state.selectedVar = picked
        state.draggedVar = picked

    @ctrl.add("set_dragged_var")
    def set_dragged_var(var_name: str, **_):
        state.draggedVar = str(var_name or "")

    @ctrl.add("toggle_variable_group")
    def toggle_variable_group(group_name: str, **_):
        name = str(group_name or "").strip()
        if not name:
            return
        collapsed = dict(state.variableGroupCollapsed or {})
        collapsed[name] = not bool(collapsed.get(name, False))
        state.variableGroupCollapsed = collapsed

    @ctrl.add("add_var_to_grid")
    def add_var_to_grid(var_name: str, **_):
        var = str(var_name or "").strip()
        if not var:
            return

        cells = normalize_grid_cells(state.gridCells)

        try:
            active = int(state.activeGridCell)
        except Exception:
            active = -1

        target = -1
        if is_valid_grid_index(active):
            if not str(cells[active].get("variable_id", "") or cells[active].get("variable_name", "") or "").strip():
                target = active

        if target < 0:
            for i, c in enumerate(cells):
                if not str(c.get("variable_id", "") or c.get("variable_name", "") or "").strip():
                    target = i
                    break

        if target < 0:
            target = active if is_valid_grid_index(active) else 0

        source_row = {}
        if str(state.detailsSelectedVarId or "") == var:
            source_row = source_row_for_key((state.selectedSourceKeys or [""])[0])
        if maybe_handle_generated_scalar_plot(
            var,
            target,
            source_row=source_row or None,
            sync_selection=True,
        ):
            set_grid_selection([target], active=target)
            return

        try:
            assign_cell(cells, target, build_grid_cell_for_variable(var, source_row=source_row or None))
        except Exception as e:
            err_cell = empty_grid_cell()
            err_cell["variable_id"] = var
            err_cell["variable_name"] = variable_label(var)
            err_cell["status"] = "error"
            err_cell["note"] = f"{type(e).__name__}: {e}"
            assign_cell(cells, target, err_cell)

        state.gridCells = normalize_grid_cells(cells)
        state.activeGridCell = target
        set_grid_selection([target], active=target)
        state.selectedVar = var
        state.draggedVar = var

    @ctrl.add("set_active_grid_cell")
    def set_active_grid_cell(cell_index: int, ignore=0, multi=0, **_):
        try:
            if int(ignore):
                return
        except Exception:
            pass

        try:
            idx = int(cell_index)
        except Exception:
            return
        if not is_valid_grid_index(idx):
            return

        cells = normalize_grid_cells(state.gridCells)
        try:
            use_multi = bool(int(multi))
        except Exception:
            use_multi = False

        if use_multi:
            if not is_selectable_grid_cell(cells, idx):
                return
            selected = normalize_grid_selection(cells=cells)
            anchor = active_grid_index(len(cells))
            if not is_selectable_grid_cell(cells, anchor):
                anchor = selected[0] if selected else idx
            start, end = sorted((anchor, idx))
            range_indices = [
                item
                for item in range(start, end + 1)
                if is_selectable_grid_cell(cells, item)
            ]
            selected_set = set(selected).union(range_indices or [idx])
            publish_grid_selection([
                item
                for item in range(len(cells))
                if item in selected_set
            ])
            state.activeGridCell = idx
            var = str(cells[idx].get("variable_id", "") or cells[idx].get("variable_name", "") or "")
            if var:
                state.selectedVar = var
                state.draggedVar = var
                update_selected_var_panels(var, preferred_source_key=str(cells[idx].get("_source_key", "") or ""))
            return

        state.activeGridCell = idx
        var = str(cells[idx].get("variable_id", "") or cells[idx].get("variable_name", "") or "")
        if var:
            set_grid_selection([idx], active=idx)
            state.selectedVar = var
            state.draggedVar = var
            update_selected_var_panels(var, preferred_source_key=str(cells[idx].get("_source_key", "") or ""))
            return

        selected = str(state.selectedVar or "").strip()
        if not selected:
            set_grid_selection([], active=idx)
            return

        source_row = {}
        if str(state.detailsSelectedVarId or "") == selected:
            source_row = source_row_for_key((state.selectedSourceKeys or [""])[0])
        if maybe_handle_generated_scalar_plot(
            selected,
            idx,
            source_row=source_row or None,
            sync_selection=True,
        ):
            set_grid_selection([idx], active=idx)
            return

        try:
            assign_cell(cells, idx, build_grid_cell_for_variable(selected, source_row=source_row or None))
        except Exception as e:
            err_cell = empty_grid_cell()
            err_cell["variable_id"] = selected
            err_cell["variable_name"] = variable_label(selected)
            err_cell["status"] = "error"
            err_cell["note"] = f"{type(e).__name__}: {e}"
            assign_cell(cells, idx, err_cell)
        state.gridCells = normalize_grid_cells(cells)
        set_grid_selection([idx], active=idx)

    @ctrl.add("toggle_timeline_driver_cell")
    def toggle_timeline_driver_cell(cell_index: int, **_):
        try:
            idx = int(cell_index)
        except Exception:
            return
        if not is_valid_grid_index(idx):
            return
        cells = normalize_grid_cells(state.gridCells)
        cell = cells[idx] if 0 <= idx < len(cells) else {}
        if not str(cell.get("variable_id", "") or cell.get("variable_name", "") or "").strip():
            return
        if not cell_has_timeline_samples(cell):
            return
        try:
            current = int(state.timelineDriverCell)
        except Exception:
            current = -1
        state.timelineDriverCell = -1 if current == idx else idx

    @ctrl.add("clear_grid_cell")
    def clear_grid_cell(cell_index: int, **_):
        try:
            idx = int(cell_index)
        except Exception:
            return
        if not is_valid_grid_index(idx):
            return

        clear_timeline_driver_if_cell(idx)
        cells = normalize_grid_cells(state.gridCells)
        assign_cell(cells, idx, empty_grid_cell())
        state.gridCells = normalize_grid_cells(cells)
        publish_grid_selection([item for item in normalize_grid_selection(cells=list(state.gridCells or [])) if item != idx])

    @ctrl.add("move_grid_cell")
    def move_grid_cell(from_index: int, to_index: int, **_):
        try:
            src = int(from_index)
            dst = int(to_index)
        except Exception:
            return
        if not is_valid_grid_index(src) or not is_valid_grid_index(dst):
            return
        if src == dst:
            return

        cells = normalize_grid_cells(state.gridCells)
        source = dict(cells[src] or {})
        if not str(source.get("variable_id", "") or source.get("variable_name", "") or "").strip():
            return

        # Move + overwrite: destination takes source tile, source is cleared.
        clear_timeline_driver_if_cell(src)
        clear_timeline_driver_if_cell(dst)
        assign_cell(cells, dst, source)
        assign_cell(cells, src, empty_grid_cell())
        state.gridCells = normalize_grid_cells(cells)
        state.activeGridCell = dst
        set_grid_selection([dst], active=dst)

    @ctrl.trigger("move_grid_cell_trigger")
    def move_grid_cell_trigger(from_index, to_index, **_):
        move_grid_cell(from_index, to_index)

    @ctrl.add("add_grid_row")
    def add_grid_row(**_):
        rows, cols = grid_dimensions()
        if rows >= GRID_MAX_ROWS:
            return

        cells = normalize_grid_cells(state.gridCells, rows, cols)
        active = active_grid_index(rows * cols)
        if normalize_grid_layout_mode() == "spanning":
            set_grid_layout(rows + 1, cols, cells, active)
            return

        new_cells = list(cells)
        new_cells.extend(empty_grid_cell() for _ in range(cols))
        set_grid_layout(rows + 1, cols, new_cells, active)

    def active_after_spanning_axis_removal(
        cells: List[Dict[str, Any]],
        active: int,
        rows: int,
        cols: int,
        remove_row: Optional[int] = None,
        remove_col: Optional[int] = None,
    ) -> int:
        if active < 0 or active >= len(cells):
            return -1
        cell = dict(cells[active] or {})
        if bool(cell.get("grid_hidden", False)):
            return -1

        row = clamp_int(cell.get("grid_row", 1), 1, 1, rows)
        col = clamp_int(cell.get("grid_col", 1), 1, 1, cols)
        row_span = clamp_int(cell.get("row_span", 1), 1, 1, max(1, rows - row + 1))
        col_span = clamp_int(cell.get("col_span", 1), 1, 1, max(1, cols - col + 1))

        if remove_row is not None:
            removed = remove_row + 1
            if row > removed:
                row -= 1
            elif row <= removed < row + row_span:
                row_span -= 1
                if row_span < 1:
                    return -1

        if remove_col is not None:
            removed = remove_col + 1
            if col > removed:
                col -= 1
            elif col <= removed < col + col_span:
                col_span -= 1
                if col_span < 1:
                    return -1

        new_cols = cols - 1 if remove_col is not None else cols
        new_rows = rows - 1 if remove_row is not None else rows
        if row < 1 or col < 1 or row > new_rows or col > new_cols:
            return -1
        return (row - 1) * new_cols + (col - 1)

    def remove_spanning_axis(
        cells: List[Dict[str, Any]],
        rows: int,
        cols: int,
        remove_row: Optional[int] = None,
        remove_col: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        new_rows = rows - 1 if remove_row is not None else rows
        new_cols = cols - 1 if remove_col is not None else cols
        adjusted: List[Dict[str, Any]] = []

        for raw_cell in cells:
            cell = dict(raw_cell or {})
            if bool(cell.get("grid_hidden", False)):
                continue

            row = clamp_int(cell.get("grid_row", 1), 1, 1, rows)
            col = clamp_int(cell.get("grid_col", 1), 1, 1, cols)
            row_span = clamp_int(cell.get("row_span", 1), 1, 1, max(1, rows - row + 1))
            col_span = clamp_int(cell.get("col_span", 1), 1, 1, max(1, cols - col + 1))

            if remove_row is not None:
                removed = remove_row + 1
                if row > removed:
                    row -= 1
                elif row <= removed < row + row_span:
                    row_span -= 1
                    if row_span < 1:
                        continue

            if remove_col is not None:
                removed = remove_col + 1
                if col > removed:
                    col -= 1
                elif col <= removed < col + col_span:
                    col_span -= 1
                    if col_span < 1:
                        continue

            if row < 1 or col < 1 or row > new_rows or col > new_cols:
                continue

            cell["grid_row"] = row
            cell["grid_col"] = col
            cell["row_span"] = min(row_span, max(1, new_rows - row + 1))
            cell["col_span"] = min(col_span, max(1, new_cols - col + 1))
            cell["grid_hidden"] = False
            adjusted.append(cell)

        return rebuild_spanning_cells(adjusted, new_rows, new_cols)

    @ctrl.add("delete_grid_row")
    def delete_grid_row(**_):
        rows, cols = grid_dimensions()
        if rows <= GRID_MIN_ROWS:
            return

        cells = normalize_grid_cells(state.gridCells, rows, cols)
        active = active_grid_index(rows * cols)
        remove_row = (active // cols) if active >= 0 else rows - 1
        drop_grid_track("row", remove_row)

        if normalize_grid_layout_mode() == "spanning":
            new_active = active_after_spanning_axis_removal(
                cells,
                active,
                rows,
                cols,
                remove_row=remove_row,
            )
            set_grid_layout(
                rows - 1,
                cols,
                remove_spanning_axis(cells, rows, cols, remove_row=remove_row),
                new_active,
            )
            return

        new_cells: List[Dict[str, Any]] = []
        for row in range(rows):
            if row == remove_row:
                continue
            start = row * cols
            new_cells.extend(cells[start : start + cols])

        new_active = -1
        if active >= 0:
            active_row = active // cols
            active_col = active % cols
            if active_row != remove_row:
                new_row = active_row - (1 if active_row > remove_row else 0)
                new_active = new_row * cols + active_col

        set_grid_layout(rows - 1, cols, new_cells, new_active)

    @ctrl.add("add_grid_column")
    def add_grid_column(**_):
        rows, cols = grid_dimensions()
        if cols >= GRID_MAX_COLS:
            return

        cells = normalize_grid_cells(state.gridCells, rows, cols)
        active = active_grid_index(rows * cols)
        if normalize_grid_layout_mode() == "spanning":
            set_grid_layout(rows, cols + 1, cells, active)
            return

        new_cells: List[Dict[str, Any]] = []
        for row in range(rows):
            start = row * cols
            new_cells.extend(cells[start : start + cols])
            new_cells.append(empty_grid_cell())

        new_active = -1
        if active >= 0:
            active_row = active // cols
            active_col = active % cols
            new_active = active_row * (cols + 1) + active_col

        set_grid_layout(rows, cols + 1, new_cells, new_active)

    @ctrl.add("delete_grid_column")
    def delete_grid_column(**_):
        rows, cols = grid_dimensions()
        if cols <= GRID_MIN_COLS:
            return

        cells = normalize_grid_cells(state.gridCells, rows, cols)
        active = active_grid_index(rows * cols)
        remove_col = (active % cols) if active >= 0 else cols - 1
        drop_grid_track("column", remove_col)

        if normalize_grid_layout_mode() == "spanning":
            new_active = active_after_spanning_axis_removal(
                cells,
                active,
                rows,
                cols,
                remove_col=remove_col,
            )
            set_grid_layout(
                rows,
                cols - 1,
                remove_spanning_axis(cells, rows, cols, remove_col=remove_col),
                new_active,
            )
            return

        new_cells: List[Dict[str, Any]] = []
        for row in range(rows):
            start = row * cols
            for col in range(cols):
                if col != remove_col:
                    new_cells.append(cells[start + col])

        new_active = -1
        if active >= 0:
            active_row = active // cols
            active_col = active % cols
            if active_col != remove_col:
                new_col = active_col - (1 if active_col > remove_col else 0)
                new_active = active_row * (cols - 1) + new_col

        set_grid_layout(rows, cols - 1, new_cells, new_active)

    def can_place_span(
        cells: List[Dict[str, Any]],
        idx: int,
        row: int,
        col: int,
        row_span: int,
        col_span: int,
        rows: int,
        cols: int,
    ) -> bool:
        if row < 1 or col < 1 or row_span < 1 or col_span < 1:
            return False
        if row + row_span - 1 > rows or col + col_span - 1 > cols:
            return False

        requested = set(area_slots(row, col, row_span, col_span, cols))
        for other_idx, raw_cell in enumerate(cells):
            if other_idx == idx:
                continue
            cell = dict(raw_cell or {})
            if bool(cell.get("grid_hidden", False)):
                continue
            other_row = clamp_int(cell.get("grid_row", 1), 1, 1, rows)
            other_col = clamp_int(cell.get("grid_col", 1), 1, 1, cols)
            other_row_span = clamp_int(cell.get("row_span", 1), 1, 1, max(1, rows - other_row + 1))
            other_col_span = clamp_int(cell.get("col_span", 1), 1, 1, max(1, cols - other_col + 1))
            if not cell_has_content(cell) and other_row_span == 1 and other_col_span == 1:
                continue
            other_slots = set(area_slots(other_row, other_col, other_row_span, other_col_span, cols))
            if requested.intersection(other_slots):
                return False
        return True

    def update_grid_cell_span(
        cell_index: int,
        row_span: Optional[int] = None,
        col_span: Optional[int] = None,
    ) -> bool:
        try:
            idx = int(cell_index)
        except Exception:
            return False
        if not is_valid_grid_index(idx):
            return False
        if normalize_grid_layout_mode() != "spanning":
            return False

        rows, cols = grid_dimensions()
        cells = normalize_grid_cells(state.gridCells, rows, cols)
        cell = dict(cells[idx] or {})
        if bool(cell.get("grid_hidden", False)):
            return False

        row = clamp_int(cell.get("grid_row", 1), 1, 1, rows)
        col = clamp_int(cell.get("grid_col", 1), 1, 1, cols)
        new_row_span = clamp_int(
            row_span if row_span is not None else cell.get("row_span", 1),
            1,
            1,
            max(1, rows - row + 1),
        )
        new_col_span = clamp_int(
            col_span if col_span is not None else cell.get("col_span", 1),
            1,
            1,
            max(1, cols - col + 1),
        )
        if not can_place_span(cells, idx, row, col, new_row_span, new_col_span, rows, cols):
            return False

        cell["row_span"] = new_row_span
        cell["col_span"] = new_col_span
        cells[idx] = cell
        state.gridCells = rebuild_spanning_cells(cells, rows, cols)
        state.activeGridCell = idx
        publish_grid_selection(normalize_grid_selection(cells=list(state.gridCells or [])))
        return True

    @ctrl.add("span_grid_cell_right")
    def span_grid_cell_right(cell_index: int, **_):
        rows, cols = grid_dimensions()
        cells = normalize_grid_cells(state.gridCells, rows, cols)
        try:
            idx = int(cell_index)
        except Exception:
            return
        if not is_valid_grid_index(idx):
            return
        cell = dict(cells[idx] or {})
        update_grid_cell_span(idx, col_span=clamp_int(cell.get("col_span", 1), 1, 1, cols) + 1)

    @ctrl.add("span_grid_cell_down")
    def span_grid_cell_down(cell_index: int, **_):
        rows, cols = grid_dimensions()
        cells = normalize_grid_cells(state.gridCells, rows, cols)
        try:
            idx = int(cell_index)
        except Exception:
            return
        if not is_valid_grid_index(idx):
            return
        cell = dict(cells[idx] or {})
        update_grid_cell_span(idx, row_span=clamp_int(cell.get("row_span", 1), 1, 1, rows) + 1)

    @ctrl.add("shrink_grid_cell_width")
    def shrink_grid_cell_width(cell_index: int, **_):
        rows, cols = grid_dimensions()
        cells = normalize_grid_cells(state.gridCells, rows, cols)
        try:
            idx = int(cell_index)
        except Exception:
            return
        if not is_valid_grid_index(idx):
            return
        cell = dict(cells[idx] or {})
        update_grid_cell_span(idx, col_span=clamp_int(cell.get("col_span", 1), 1, 1, cols) - 1)

    @ctrl.add("shrink_grid_cell_height")
    def shrink_grid_cell_height(cell_index: int, **_):
        rows, cols = grid_dimensions()
        cells = normalize_grid_cells(state.gridCells, rows, cols)
        try:
            idx = int(cell_index)
        except Exception:
            return
        if not is_valid_grid_index(idx):
            return
        cell = dict(cells[idx] or {})
        update_grid_cell_span(idx, row_span=clamp_int(cell.get("row_span", 1), 1, 1, rows) - 1)

    @ctrl.add("reset_grid_cell_span")
    def reset_grid_cell_span(cell_index: int, **_):
        update_grid_cell_span(cell_index, row_span=1, col_span=1)

    @ctrl.add("assign_var_to_grid_cell")
    def assign_var_to_grid_cell(cell_index: int, var_name: str, sync_selection: bool = True, **_):
        try:
            idx = int(cell_index)
        except Exception:
            return
        if not is_valid_grid_index(idx):
            return

        var = str(var_name or "").strip()
        if not var:
            var = str(state.draggedVar or "").strip()
        if not var:
            var = str(state.selectedVar or "").strip()
        if not var:
            return

        cells = normalize_grid_cells(state.gridCells)
        source_row = {}
        if str(state.detailsSelectedVarId or "") == var:
            source_row = source_row_for_key((state.selectedSourceKeys or [""])[0])
        if maybe_handle_generated_scalar_plot(
            var,
            idx,
            source_row=source_row or None,
            sync_selection=sync_selection,
        ):
            set_grid_selection([idx], active=idx)
            return

        try:
            assign_cell(cells, idx, build_grid_cell_for_variable(var, source_row=source_row or None))
        except Exception as e:
            err_cell = empty_grid_cell()
            err_cell["variable_id"] = var
            err_cell["variable_name"] = variable_label(var)
            err_cell["status"] = "error"
            err_cell["note"] = f"{type(e).__name__}: {e}"
            assign_cell(cells, idx, err_cell)
        state.gridCells = normalize_grid_cells(cells)
        state.activeGridCell = idx
        set_grid_selection([idx], active=idx)
        if sync_selection:
            state.selectedVar = var
            state.draggedVar = var

    @ctrl.trigger("assign_var_to_grid_cell_trigger")
    def assign_var_to_grid_cell_trigger(var_name, cell_index, **_):
        assign_var_to_grid_cell(cell_index, var_name, sync_selection=False)
        # After drag/drop, clear variable highlight in the left panel.
        state.selectedVar = ""
        state.draggedVar = ""

    @ctrl.add("pick_grid_cell_visualization")
    def pick_grid_cell_visualization(cell_index: int, value=None, **_):
        try:
            idx = int(cell_index)
        except Exception:
            return
        if not is_valid_grid_index(idx):
            return

        cells = normalize_grid_cells(state.gridCells)
        var = str(cells[idx].get("variable_id", "") or cells[idx].get("variable_name", "") or "").strip()
        if not var:
            return

        picked = value
        if isinstance(picked, dict):
            picked = picked.get("value", "")
        picked = str(picked or "")

        try:
            existing_cell = cells[idx]
            current_filter = source_filter_from_cell(existing_cell)
            source_row = {}
            if current_filter:
                current_vis_names = visualization_names_for_source_filter(var, current_filter)
                if picked not in current_vis_names:
                    source_row = source_row_for_visualization_pick(var, picked)

            if source_row:
                new_cell = build_grid_cell_for_variable(var, preferred_vis=picked, source_row=source_row)
            else:
                new_cell = build_grid_cell_for_variable(var, preferred_vis=picked, existing_cell=existing_cell)
            assign_cell(cells, idx, new_cell)
        except Exception as e:
            err_cell = empty_grid_cell()
            err_cell["variable_id"] = var
            err_cell["variable_name"] = variable_label(var)
            err_cell["status"] = "error"
            err_cell["note"] = f"{type(e).__name__}: {e}"
            assign_cell(cells, idx, err_cell)

        state.gridCells = normalize_grid_cells(cells)
        state.activeGridCell = idx
        set_grid_selection([idx], active=idx)
        state.selectedVar = var

    @ctrl.add("hide_context_menu")
    def hide_context_menu(**_):
        clear_context_menu_state()

    @ctrl.trigger("hide_context_menu_trigger")
    def hide_context_menu_trigger(**_):
        hide_context_menu()

    @ctrl.trigger("show_item_context_menu")
    def show_item_context_menu(item_name, x, y, **_):
        item = str(item_name or "").strip()
        if not item:
            return
        try:
            px = int(float(x))
        except Exception:
            px = 0
        try:
            py = int(float(y))
        except Exception:
            py = 0

        state.contextMenuKind = "item"
        state.contextMenuItem = item
        state.contextMenuItemLabel = variable_label(item)
        state.contextMenuCellIndex = -1
        state.contextMenuCellHasVariable = False
        state.contextMenuCellCanAddSource = False
        state.contextMenuCellVisualizationOptions = []
        state.contextMenuCellSelectedVisualization = ""
        state.contextMenuCellSourcePlugins = []
        state.contextMenuX = px
        state.contextMenuY = py
        state.contextMenuVisible = True

    @ctrl.trigger("show_cell_context_menu")
    def show_cell_context_menu(cell_index, x, y, **_):
        try:
            idx = int(cell_index)
        except Exception:
            return
        if not is_valid_grid_index(idx):
            return
        try:
            px = int(float(x))
        except Exception:
            px = 0
        try:
            py = int(float(y))
        except Exception:
            py = 0

        cells = normalize_grid_cells(state.gridCells)
        cell = dict(cells[idx] or {})
        has_var = bool(str(cell.get("variable_id", "") or cell.get("variable_name", "") or "").strip())
        label = str(cell.get("variable_name", "") or "").strip() or f"Cell {idx + 1}"
        vis_opts = []
        for raw_vis in (cell.get("visualization_options", []) or []):
            vis = str(raw_vis or "").strip()
            if vis and vis not in vis_opts:
                vis_opts.append(vis)
        selected_vis = str(cell.get("selected_visualization", "") or cell.get("visualization_name", "") or "").strip()
        if selected_vis and selected_vis not in vis_opts:
            vis_opts.append(selected_vis)
        targets = source_dialog_targets_for_anchor(idx, cells)
        can_add_source = bool(targets) and all(is_generated_plot1d_cell(cells[target]) for target in targets)
        is_plugin_cell = is_plugin_visualization(selected_vis)
        can_plot_settings = has_var and (
            str(cell.get("media_type", "") or "") == "plot1d" or is_plugin_cell
        )
        can_scalar_field_settings = has_var and is_scalar_field_cell(cell)
        media_type = str(cell.get("media_type", "") or "")
        can_reset_view = has_var and (
            media_type == "plot1d"
            or (bool(str(cell.get("src", "") or "").strip()) and media_type != "plot1d")
        )
        source_plugin_entries = source_plugin_menu_entries_for_cell(cell) if has_var else []

        state.contextMenuKind = "cell"
        state.contextMenuItem = label
        state.contextMenuItemLabel = label
        state.contextMenuCellIndex = idx
        state.contextMenuCellHasVariable = has_var
        state.contextMenuCellCanAddSource = can_add_source
        state.contextMenuCellCanPlotSettings = can_plot_settings
        state.contextMenuCellCanScalarFieldSettings = can_scalar_field_settings
        state.contextMenuCellCanResetView = can_reset_view
        state.contextMenuCellVisualizationOptions = vis_opts
        state.contextMenuCellSelectedVisualization = selected_vis
        state.contextMenuCellSourcePlugins = source_plugin_entries
        state.contextMenuX = px
        state.contextMenuY = py
        state.contextMenuVisible = True

    @ctrl.add("context_menu_item_add")
    def context_menu_item_add(**_):
        item = str(state.contextMenuItem or "").strip()
        if item:
            add_var_to_grid(item)
        hide_context_menu()

    @ctrl.add("context_menu_item_select")
    def context_menu_item_select(**_):
        item = str(state.contextMenuItem or "").strip()
        if item:
            state.selectedVar = item
            state.draggedVar = item
        hide_context_menu()

    @ctrl.add("context_menu_cell_clear")
    def context_menu_cell_clear(**_):
        try:
            idx = int(state.contextMenuCellIndex)
        except Exception:
            idx = -1
        if is_valid_grid_index(idx):
            clear_grid_cell(idx)
        hide_context_menu()

    @ctrl.add("context_menu_cell_select")
    def context_menu_cell_select(**_):
        try:
            idx = int(state.contextMenuCellIndex)
        except Exception:
            idx = -1
        if is_valid_grid_index(idx):
            set_active_grid_cell(idx, 0)
        hide_context_menu()

    @ctrl.add("context_menu_cell_reset_view")
    def context_menu_cell_reset_view(**_):
        try:
            idx = int(state.contextMenuCellIndex)
        except Exception:
            idx = -1
        if is_valid_grid_index(idx):
            state.resetViewRequest = {"cell_index": idx, "nonce": int(getattr(state, "resetViewRequestNonce", 0) or 0) + 1}
            state.resetViewRequestNonce = state.resetViewRequest["nonce"]
        hide_context_menu()

    def context_menu_cell_index() -> int:
        try:
            idx = int(state.contextMenuCellIndex)
        except Exception:
            return -1
        return idx if is_valid_grid_index(idx) else -1

    @ctrl.add("context_menu_cell_span_right")
    def context_menu_cell_span_right(**_):
        idx = context_menu_cell_index()
        if idx >= 0:
            span_grid_cell_right(idx)
        hide_context_menu()

    @ctrl.add("context_menu_cell_span_down")
    def context_menu_cell_span_down(**_):
        idx = context_menu_cell_index()
        if idx >= 0:
            span_grid_cell_down(idx)
        hide_context_menu()

    @ctrl.add("context_menu_cell_shrink_width")
    def context_menu_cell_shrink_width(**_):
        idx = context_menu_cell_index()
        if idx >= 0:
            shrink_grid_cell_width(idx)
        hide_context_menu()

    @ctrl.add("context_menu_cell_shrink_height")
    def context_menu_cell_shrink_height(**_):
        idx = context_menu_cell_index()
        if idx >= 0:
            shrink_grid_cell_height(idx)
        hide_context_menu()

    @ctrl.add("context_menu_cell_reset_span")
    def context_menu_cell_reset_span(**_):
        idx = context_menu_cell_index()
        if idx >= 0:
            reset_grid_cell_span(idx)
        hide_context_menu()

    @ctrl.add("context_menu_cell_sources")
    def context_menu_cell_sources(**_):
        try:
            idx = int(state.contextMenuCellIndex)
        except Exception:
            idx = -1
        if not is_valid_grid_index(idx):
            hide_context_menu()
            return

        open_source_dialog_for_cell(idx, prefer_multi=False)
        hide_context_menu()

    @ctrl.add("context_menu_cell_add_source")
    def context_menu_cell_add_source(**_):
        try:
            idx = int(state.contextMenuCellIndex)
        except Exception:
            idx = -1
        if not is_valid_grid_index(idx):
            hide_context_menu()
            return

        open_source_dialog_for_cell(idx, prefer_multi=True)
        hide_context_menu()

    @ctrl.add("context_menu_cell_plot_settings")
    def context_menu_cell_plot_settings(**_):
        try:
            idx = int(state.contextMenuCellIndex)
        except Exception:
            idx = -1
        if not is_valid_grid_index(idx):
            hide_context_menu()
            return

        cells = normalize_grid_cells(state.gridCells)
        cell = dict(cells[idx] or {})
        selected_vis = str(cell.get("selected_visualization", "") or cell.get("visualization_name", "") or "")
        if str(cell.get("media_type", "") or "") != "plot1d":
            if is_plugin_visualization(selected_vis):
                state.activeGridCell = idx
                load_plugin_options_dialog(idx)
                hide_context_menu()
                return
            hide_context_menu()
            return

        state.activeGridCell = idx
        load_plot_settings_dialog(idx)
        hide_context_menu()

    @ctrl.add("context_menu_cell_scalar_field_settings")
    def context_menu_cell_scalar_field_settings(**_):
        try:
            idx = int(state.contextMenuCellIndex)
        except Exception:
            idx = -1
        if not is_valid_grid_index(idx):
            hide_context_menu()
            return

        cells = normalize_grid_cells(state.gridCells)
        cell = dict(cells[idx] or {})
        if not is_scalar_field_cell(cell):
            hide_context_menu()
            return

        state.activeGridCell = idx
        load_scalar_field_settings_dialog(idx)
        hide_context_menu()

    @ctrl.add("context_menu_cell_pick_visualization")
    def context_menu_cell_pick_visualization(value: str = "", **_):
        try:
            idx = int(state.contextMenuCellIndex)
        except Exception:
            idx = -1
        if not is_valid_grid_index(idx):
            hide_context_menu()
            return

        picked = str(value or "").strip()
        if not picked:
            hide_context_menu()
            return

        pick_grid_cell_visualization(idx, picked)
        hide_context_menu()

    @ctrl.add("context_menu_cell_run_source_plugin")
    def context_menu_cell_run_source_plugin(plugin_id: str = "", **_):
        try:
            idx = int(state.contextMenuCellIndex)
        except Exception:
            idx = -1
        if not is_valid_grid_index(idx):
            hide_context_menu()
            return

        plugin = str(plugin_id or "").strip()
        if not plugin:
            hide_context_menu()
            return

        cells = normalize_grid_cells(state.gridCells)
        existing = dict(cells[idx] or {})
        try:
            tile = build_source_plugin_grid_cell(plugin, existing)
            assign_cell(cells, idx, preserve_grid_geometry(tile, existing))
            state.gridCells = normalize_grid_cells(cells)
            state.activeGridCell = idx
        except Exception as e:
            err_cell = no_visualization_grid_cell(
                str(existing.get("variable_id", "") or existing.get("variable_name", "") or ""),
                f"Plugin {plugin} failed: {type(e).__name__}: {e}",
            )
            err_cell.update(
                {
                    k: v
                    for k, v in existing.items()
                    if k in {"source_dataset", "schema_file_group", "schema_mode", "producer", "casename", "file", "_source_key"}
                }
            )
            assign_cell(cells, idx, preserve_grid_geometry(err_cell, existing))
            state.gridCells = normalize_grid_cells(cells)
            state.activeGridCell = idx
        hide_context_menu()

    @ctrl.add("cancel_scalar_plot_generation")
    def cancel_scalar_plot_generation(**_):
        clear_pending_scalar_plot()

    @ctrl.add("confirm_scalar_plot_generation")
    def confirm_scalar_plot_generation(**_):
        var_id = str(state.pendingScalarPlotVariableId or "").strip()
        try:
            idx = int(state.pendingScalarPlotCellIndex)
        except Exception:
            idx = -1
        source_fields = dict(state.pendingScalarPlotSourceFields or {})
        sync_selection = bool(state.pendingScalarPlotSyncSelection)

        if bool(state.scalarPlotAlwaysForSession):
            state.scalarPlotPolicy = "always"

        clear_pending_scalar_plot()
        if not var_id or not is_valid_grid_index(idx):
            return

        set_generated_scalar_plot_cell(
            idx,
            var_id,
            source_fields=source_fields,
            sync_selection=sync_selection,
        )

    @ctrl.add("cancel_plot_settings")
    def cancel_plot_settings(**_):
        state.showPlotSettingsModal = False
        state.plotSettingsCellIndex = -1
        state.plotSettingsStatus = ""
        state.plotSettingsCanPluginOptions = False

    @ctrl.add("open_plot_settings_plugin_options")
    def open_plot_settings_plugin_options(**_):
        try:
            idx = int(state.plotSettingsCellIndex)
        except Exception:
            idx = -1
        if not is_valid_grid_index(idx):
            state.plotSettingsStatus = "No plot cell selected."
            return

        cells = normalize_grid_cells(state.gridCells)
        cell = dict(cells[idx] or {})
        selected_vis = str(cell.get("selected_visualization", "") or cell.get("visualization_name", "") or "")
        if not is_plugin_visualization(selected_vis):
            state.plotSettingsStatus = "Selected cell is not a plugin visualization."
            return

        state.showPlotSettingsModal = False
        load_plugin_options_dialog(idx)

    @ctrl.add("cancel_plugin_options")
    def cancel_plugin_options(**_):
        state.showPluginOptionsModal = False
        state.pluginOptionsCellIndex = -1
        state.pluginOptionsStatus = ""
        state.pluginOptionsRows = []

    @ctrl.add("reset_plugin_options")
    def reset_plugin_options(**_):
        try:
            idx = int(state.pluginOptionsCellIndex)
        except Exception:
            idx = -1
        if is_valid_grid_index(idx):
            load_plugin_options_dialog(idx, reset=True)

    @ctrl.add("update_plugin_option_value")
    def update_plugin_option_value(key: str, value: Any, **_):
        target_key = str(key or "").strip()
        if not target_key:
            return
        rows = []
        for raw_row in state.pluginOptionsRows or []:
            row = dict(raw_row or {})
            if str(row.get("key", "") or "") == target_key:
                if str(row.get("type", "") or "") == "bool":
                    row["value"] = bool(value)
                else:
                    row["value"] = str(value or "")
            rows.append(row)
        state.pluginOptionsRows = rows

    @ctrl.add("apply_plugin_options")
    def apply_plugin_options(**_):
        try:
            idx = int(state.pluginOptionsCellIndex)
        except Exception:
            idx = -1
        if not is_valid_grid_index(idx):
            state.pluginOptionsStatus = "No plugin cell selected."
            return

        cells = normalize_grid_cells(state.gridCells)
        cell = dict(cells[idx] or {})
        selected_vis = str(cell.get("selected_visualization", "") or cell.get("visualization_name", "") or "")
        if not is_plugin_visualization(selected_vis):
            state.pluginOptionsStatus = "Selected cell is not a plugin visualization."
            return

        var_id = str(cell.get("variable_id", "") or cell.get("variable_name", "") or "").strip()
        if not var_id:
            state.pluginOptionsStatus = "Selected cell has no variable."
            return

        options = plugin_options_from_rows(list(state.pluginOptionsRows or []))
        try:
            plugin_id = plugin_id_from_visualization(selected_vis)
            if plugin_scope(plugin_id) == "source":
                new_cell = build_source_plugin_grid_cell(plugin_id, cell, plugin_options=options)
            else:
                new_cell = build_plugin_grid_cell(
                    var_id,
                    selected_vis,
                    existing_cell=cell,
                    plugin_options=options,
                )
            assign_cell(cells, idx, new_cell)
        except Exception as e:
            state.pluginOptionsStatus = f"{type(e).__name__}: {e}"
            return

        state.gridCells = normalize_grid_cells(cells)
        state.activeGridCell = idx
        state.pluginOptionsStatus = ""
        state.showPluginOptionsModal = False

    @ctrl.add("cancel_scalar_field_settings")
    def cancel_scalar_field_settings(**_):
        state.showScalarFieldSettingsModal = False
        state.scalarFieldSettingsCellIndex = -1
        state.scalarFieldSettingsStatus = ""
        state.scalarFieldSettingsStatusIsError = False

    @ctrl.add("reset_scalar_field_settings")
    def reset_scalar_field_settings(**_):
        try:
            idx = int(state.scalarFieldSettingsCellIndex)
        except Exception:
            idx = -1
        if is_valid_grid_index(idx):
            load_scalar_field_settings_dialog(idx, reset=True)

    @ctrl.add("apply_scalar_field_settings")
    def apply_scalar_field_settings(**_):
        try:
            idx = int(state.scalarFieldSettingsCellIndex)
        except Exception:
            idx = -1
        if not is_valid_grid_index(idx):
            state.scalarFieldSettingsStatus = "No scalar-field cell selected."
            state.scalarFieldSettingsStatusIsError = True
            return

        cells = normalize_grid_cells(state.gridCells)
        cell = dict(cells[idx] or {})
        if not is_scalar_field_cell(cell):
            state.scalarFieldSettingsStatus = "Selected cell is not a scalar-field visualization."
            state.scalarFieldSettingsStatusIsError = True
            return

        colormap = scalar_colormap(state.scalarFieldSettingsColormap)
        range_auto = bool(state.scalarFieldSettingsRangeAuto)
        show_colorbar = bool(state.scalarFieldSettingsShowColorbar)
        show_axes = bool(state.scalarFieldSettingsShowAxes)
        min_value = finite_float(state.scalarFieldSettingsMin)
        max_value = finite_float(state.scalarFieldSettingsMax)
        if not range_auto:
            if min_value is None or max_value is None:
                state.scalarFieldSettingsStatus = "Manual range requires min and max values."
                state.scalarFieldSettingsStatusIsError = True
                return
            if min_value >= max_value:
                state.scalarFieldSettingsStatus = "Manual range must have min < max."
                state.scalarFieldSettingsStatusIsError = True
                return

        settings = normalize_scalar_field_settings(
            {
                "colormap": colormap,
                "range_auto": range_auto,
                "min": None if range_auto else min_value,
                "max": None if range_auto else max_value,
                "show_colorbar": show_colorbar,
                "show_axes": show_axes,
            }
        )
        cell["scalar_field_settings"] = settings

        var = str(cell.get("variable_id", "") or cell.get("variable_name", "") or "").strip()
        selected_vis = str(cell.get("selected_visualization", "") or cell.get("visualization_name", "") or "").strip()
        if not var or not selected_vis:
            state.scalarFieldSettingsStatus = "Cell is missing a variable or visualization."
            state.scalarFieldSettingsStatusIsError = True
            return

        try:
            new_cell = build_grid_cell_for_variable(var, preferred_vis=selected_vis, existing_cell=cell)
            assign_cell(cells, idx, new_cell)
        except Exception as e:
            state.scalarFieldSettingsStatus = f"{type(e).__name__}: {e}"
            state.scalarFieldSettingsStatusIsError = True
            return

        state.gridCells = normalize_grid_cells(cells)
        state.activeGridCell = idx
        state.scalarFieldSettingsStatus = "Applied."
        state.scalarFieldSettingsStatusIsError = False

    @ctrl.add("reset_plot_settings")
    def reset_plot_settings(**_):
        try:
            idx = int(state.plotSettingsCellIndex)
        except Exception:
            idx = -1
        if is_valid_grid_index(idx):
            load_plot_settings_dialog(idx, reset=True)

    @ctrl.add("update_plot_background_color")
    def update_plot_background_color(color: str, **_):
        state.plotSettingsBackgroundColor = clean_plot_color(
            color,
            str(state.plotSettingsBackgroundColor or "#ffffff"),
        )

    @ctrl.add("update_plot_grid_color")
    def update_plot_grid_color(color: str, **_):
        state.plotSettingsGridColor = clean_plot_color(
            color,
            str(state.plotSettingsGridColor or "#e8e8e8"),
        )

    @ctrl.add("update_plot_cursor_color")
    def update_plot_cursor_color(color: str, **_):
        state.plotSettingsCursorColor = clean_plot_color(
            color,
            str(state.plotSettingsCursorColor or "#111111"),
        )

    @ctrl.add("update_plot_series_color")
    def update_plot_series_color(key: str, color: str, **_):
        target_key = str(key or "")
        rows = []
        for raw_row in state.plotSettingsSeriesRows or []:
            row = dict(raw_row or {})
            if str(row.get("key", "") or "") == target_key:
                row["color"] = clean_plot_color(color, str(row.get("color", "") or "#1565c0"))
            rows.append(row)
        state.plotSettingsSeriesRows = rows

    @ctrl.add("update_plot_series_line_style")
    def update_plot_series_line_style(key: str, line_style: str, **_):
        target_key = str(key or "")
        rows = []
        for raw_row in state.plotSettingsSeriesRows or []:
            row = dict(raw_row or {})
            if str(row.get("key", "") or "") == target_key:
                row["line_style"] = clean_line_style(line_style)
            rows.append(row)
        state.plotSettingsSeriesRows = rows

    @ctrl.add("apply_plot_settings")
    def apply_plot_settings(**_):
        try:
            idx = int(state.plotSettingsCellIndex)
        except Exception:
            idx = -1
        if not is_valid_grid_index(idx):
            state.plotSettingsStatus = "No plot cell selected."
            return

        cells = normalize_grid_cells(state.gridCells)
        cell = dict(cells[idx] or {})
        if str(cell.get("media_type", "") or "") != "plot1d":
            state.plotSettingsStatus = "Selected cell is not a 1D plot."
            return

        x_auto = bool(state.plotSettingsXAuto)
        y_auto = bool(state.plotSettingsYAuto)
        x_min = finite_float(state.plotSettingsXMin)
        x_max = finite_float(state.plotSettingsXMax)
        y_min = finite_float(state.plotSettingsYMin)
        y_max = finite_float(state.plotSettingsYMax)
        x_scale = str(state.plotSettingsXScale or "linear").strip().lower()
        y_scale = str(state.plotSettingsYScale or "linear").strip().lower()
        if x_scale not in {"linear", "log"}:
            x_scale = "linear"
        if y_scale not in {"linear", "log"}:
            y_scale = "linear"

        if not x_auto:
            if x_min is None or x_max is None:
                state.plotSettingsStatus = "Manual X range requires min and max values."
                return
            if x_min >= x_max:
                state.plotSettingsStatus = "Manual X range must have min < max."
                return
        if not y_auto:
            if y_min is None or y_max is None:
                state.plotSettingsStatus = "Manual Y range requires min and max values."
                return
            if y_min >= y_max:
                state.plotSettingsStatus = "Manual Y range must have min < max."
                return

        if x_scale == "log":
            if not axis_has_positive_data(cell, "x"):
                state.plotSettingsStatus = "X log scale requires positive X values."
                return
            if not x_auto and (x_min is None or x_max is None or x_min <= 0 or x_max <= 0):
                state.plotSettingsStatus = "Manual X log range must be positive."
                return
        if y_scale == "log":
            if not axis_has_positive_data(cell, "y"):
                state.plotSettingsStatus = "Y log scale requires positive Y values."
                return
            if not y_auto and (y_min is None or y_max is None or y_min <= 0 or y_max <= 0):
                state.plotSettingsStatus = "Manual Y log range must be positive."
                return

        line_width = finite_float(state.plotSettingsLineWidth)
        if line_width is None:
            state.plotSettingsStatus = "Line width must be a number."
            return
        line_width = max(0.5, min(8.0, line_width))
        background_color = clean_plot_color(state.plotSettingsBackgroundColor, "#ffffff")
        grid_color = clean_plot_color(state.plotSettingsGridColor, "#e8e8e8")
        cursor_color = clean_plot_color(state.plotSettingsCursorColor, "#111111")

        series_colors: Dict[str, str] = {}
        series_styles: Dict[str, Dict[str, str]] = {}
        current_settings = normalize_plot_settings(cell, cell.get("plot_settings", {}))
        current_colors = current_settings.get("series_colors", {})
        current_colors = current_colors if isinstance(current_colors, dict) else {}
        current_styles = current_settings.get("series_styles", {})
        current_styles = current_styles if isinstance(current_styles, dict) else {}
        for row in state.plotSettingsSeriesRows or []:
            item = dict(row or {})
            key = str(item.get("key", "") or "")
            if not key:
                continue
            current_style = current_styles.get(key, {})
            current_style = current_style if isinstance(current_style, dict) else {}
            color = clean_plot_color(
                item.get("color", ""),
                str(current_style.get("color", "") or current_colors.get(key, "") or "#1565c0"),
            )
            line_style = clean_line_style(item.get("line_style", current_style.get("line_style", "solid")))
            series_colors[key] = color
            series_styles[key] = {
                "color": color,
                "line_style": line_style,
            }

        cell["plot_settings"] = normalize_plot_settings(
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
                "show_grid": bool(state.plotSettingsShowGrid),
                "show_cursor": bool(state.plotSettingsShowCursor),
                "background_color": background_color,
                "grid_color": grid_color,
                "cursor_color": cursor_color,
            },
        )
        cells[idx] = cell
        state.gridCells = normalize_grid_cells(cells)
        state.activeGridCell = idx
        state.plotSettingsStatus = ""
        state.showPlotSettingsModal = False

    @ctrl.add("toggle_sources")
    def toggle_sources(**_):
        opening = not bool(state.showSourcesModal)
        state.showSourcesModal = opening
        if opening:
            try:
                idx = int(state.activeGridCell)
            except Exception:
                idx = -1
            state.showSourcesModal = False
            if is_valid_grid_index(idx):
                open_source_dialog_for_cell(idx, prefer_multi=True)

    @ctrl.add("cancel_source_dialog")
    def cancel_source_dialog(**_):
        valid_keys = source_row_keys()
        restored = [
            key
            for key in normalize_source_keys(state.sourceDialogInitialSelectedSourceKeys or [])
            if key in valid_keys
        ]
        state.selectedSourceKeys = restored
        update_selected_source_label()
        state.sourceDialogStatus = ""
        state.sourceDialogStatusIsError = False
        state.showSourcesModal = False

    @ctrl.add("apply_source_dialog")
    def apply_source_dialog(**_):
        mode = str(state.sourceDialogMode or "single")
        valid_keys = source_row_keys()
        selected = [
            key
            for key in normalize_source_keys(state.selectedSourceKeys or [])
            if key in valid_keys
        ]
        targets = source_dialog_target_indices()
        cells = normalize_grid_cells(state.gridCells)
        allow_multi_sources = mode == "add" and source_dialog_multi_source_allowed(targets, cells)
        if not allow_multi_sources:
            selected = selected[:1]

        applied, failures = apply_source_rows_to_targets(
            targets,
            selected,
            allow_multi_sources,
        )

        state.sourceDialogInitialSelectedSourceKeys = selected
        if failures:
            prefix = f"Applied to {applied} cell{'s' if applied != 1 else ''}; " if applied else ""
            state.sourceDialogStatus = prefix + "Failed: " + "; ".join(failures[:4])
            if len(failures) > 4:
                state.sourceDialogStatus += f"; {len(failures) - 4} more"
            state.sourceDialogStatusIsError = True
            return

        state.sourceDialogStatus = f"Applied to {applied} cell{'s' if applied != 1 else ''}."
        state.sourceDialogStatusIsError = False
        state.showSourcesModal = False

    @ctrl.add("clear_source_filter")
    def clear_source_filter(**_):
        select_first_source()
        update_selected_var_panels(state.selectedVar)

    @ctrl.add("apply_source_dialog_filter")
    def apply_source_dialog_filter(**_):
        state.sourceFilterText = str(state.sourceFilterDraftText or "").strip()
        state.sourceFilterError = ""
        apply_source_filter_and_sort()

    @ctrl.add("show_query_help")
    def show_query_help(**_):
        show_help("Query Help")

    @ctrl.add("show_source_filter_help")
    def show_source_filter_help(**_):
        show_help("Source Filter Help")

    @ctrl.add("close_help_modal")
    def close_help_modal(**_):
        state.showHelpModal = False

    def sync_add_source_selection_to_cell(var_id: str, idx: int, selected: List[str]) -> None:
        if not var_id or not is_valid_grid_index(idx):
            return

        cells = normalize_grid_cells(state.gridCells)
        cell_var = str(cells[idx].get("variable_id", "") or cells[idx].get("variable_name", "") or "").strip()
        selected_vis = str(cells[idx].get("selected_visualization", "") or cells[idx].get("visualization_name", "") or "")
        visualization_name = str(cells[idx].get("visualization_name", "") or selected_vis)
        if cell_var != var_id or (
            selected_vis != GENERATED_SCALAR_PLOT_VIS and visualization_name != GENERATED_SCALAR_PLOT_VIS
        ):
            return

        rows = source_rows_for_keys(selected)
        if rows:
            set_generated_scalar_plot_sources_cell(
                idx,
                var_id,
                rows,
                sync_selection=False,
            )
            update_selected_var_panels(var_id, preferred_source_keys=selected)

    @ctrl.add("toggle_add_source")
    def toggle_add_source(key: str, **_):
        k = str(key or "").strip()
        if not k:
            return

        valid_keys = source_row_keys()
        if k not in valid_keys:
            return

        selected = [key for key in normalize_source_keys(state.selectedSourceKeys or []) if key in valid_keys]

        if k in selected:
            selected = [key for key in selected if key != k]
        else:
            selected.append(k)
        selected_set = set(selected)
        selected = [key for key in valid_keys if key in selected_set]

        state.sourceDialogMode = "add"
        state.selectedSourceKeys = selected
        update_selected_source_label()

    @ctrl.add("select_all_sources")
    def select_all_sources(**_):
        visible_keys = visible_source_row_keys()
        if not visible_keys:
            return

        valid_keys = source_row_keys()
        selected = [
            key
            for key in normalize_source_keys(state.selectedSourceKeys or [])
            if key in valid_keys
        ]
        selected_set = set(selected).union(visible_keys)
        selected = [key for key in valid_keys if key in selected_set]

        state.sourceDialogMode = "add"
        state.selectedSourceKeys = selected
        update_selected_source_label()

    @ctrl.add("clear_all_sources")
    def clear_all_sources(**_):
        state.sourceDialogMode = "add"
        state.selectedSourceKeys = []
        update_selected_source_label()

    def commit_single_source_selection(key: str, idx: int = -1) -> None:
        row = source_row_for_key(key)
        state.sourceDialogMode = "single"
        select_source_key(key)

        var_id = str(state.detailsSelectedVarId or state.selectedVar or "").strip()
        if not is_valid_grid_index(idx):
            try:
                idx = int(state.sourceDialogCellIndex)
            except Exception:
                idx = -1
        if not is_valid_grid_index(idx):
            try:
                idx = int(state.activeGridCell)
            except Exception:
                idx = -1

        if row and var_id and is_valid_grid_index(idx):
            cells = normalize_grid_cells(state.gridCells)
            cell_var = str(cells[idx].get("variable_id", "") or cells[idx].get("variable_name", "") or "").strip()
            if cell_var == var_id:
                selected_vis = str(cells[idx].get("selected_visualization", "") or "")
                visualization_name = str(cells[idx].get("visualization_name", "") or selected_vis)
                if visualization_name == GENERATED_SCALAR_PLOT_VIS or selected_vis == GENERATED_SCALAR_PLOT_VIS:
                    set_generated_scalar_plot_cell(
                        idx,
                        var_id,
                        source_fields=source_fields_from_row(row),
                        sync_selection=False,
                    )
                else:
                    assign_cell(
                        cells,
                        idx,
                        build_grid_cell_for_variable(
                            var_id,
                            preferred_vis=selected_vis,
                            source_row=row,
                        ),
                    )
                    state.gridCells = normalize_grid_cells(cells)

        update_selected_var_panels(var_id, preferred_source_key=str(key or ""))

    @ctrl.add("select_source")
    def select_source(key: str, **_):
        commit_single_source_selection(key)
        state.showSourcesModal = True

    @ctrl.add("source_dialog_select")
    def source_dialog_select(key: str, **_):
        if str(state.sourceDialogMode or "single") == "add":
            toggle_add_source(key)
        else:
            state.sourceDialogMode = "single"
            select_source_key(key)

    @ctrl.add("toggle_source_visibility")
    def toggle_source_visibility(key: str, **_):
        select_source(key)

    @ctrl.add("toggle_movie_details")
    def toggle_movie_details(key: str, **_):
        k = str(key or "")
        current = bool((state.movieDetailsOpen or {}).get(k, False))
        state.movieDetailsOpen = {**(state.movieDetailsOpen or {}), k: (not current)}

    @ctrl.add("pick_tile_visualization")
    def pick_tile_visualization(source_key: str, value=None, **_):
        key = str(source_key or "")
        if not key:
            return

        picked = value
        if isinstance(picked, dict):
            picked = picked.get("value", "")
        picked = str(picked or "")

        by_source = dict(state.tileVisualizationBySource or {})
        by_source[key] = picked
        state.tileVisualizationBySource = by_source

        if state.selectedVar:
            update_selected_var_panels(state.selectedVar)

    @ctrl.add("run_query")
    def run_query(**_):
        q = (state.queryText or "").strip()

        if not q:
            state.queryFilter = {}
            state.querySourceFilters = []
            state.querySourceRestrictionFilter = {}
            state.querySourceRestrictionCount = 0
            state.queryError = ""
            state.queryStatus = "Query cleared"
            state.queryViewLabel = "ALL"
            refresh_after_variable_catalog_change()
            return

        try:
            query_filter, source_filters = python_query_to_filters(q)
            source_summary = db.source_restriction_summary(source_filters)
            source_count = int(source_summary.get("count", 0) or 0)
            state.queryFilter = query_filter
            state.querySourceFilters = source_filters
            state.querySourceRestrictionFilter = dict(source_summary.get("filter", {}) or {}) if source_filters else {}
            state.querySourceRestrictionCount = source_count if source_filters else 0
            state.queryError = ""
            state.queryStatus = (
                f"Query OK · {source_count} source run{'s' if source_count != 1 else ''}"
                if source_filters
                else "Query OK"
            )
            state.queryViewLabel = q
        except Exception as e:
            state.queryFilter = {}
            state.querySourceFilters = []
            state.querySourceRestrictionFilter = {}
            state.querySourceRestrictionCount = 0
            state.queryError = f"{type(e).__name__}: {e}"
            state.queryStatus = "Query ERROR"
            state.queryViewLabel = "ALL"
            return

        refresh_after_variable_catalog_change()

    @ctrl.add("clear_query")
    def clear_query(**_):
        state.queryText = ""
        state.queryFilter = {}
        state.querySourceFilters = []
        state.querySourceRestrictionFilter = {}
        state.querySourceRestrictionCount = 0
        state.queryError = ""
        state.queryStatus = "Query cleared"
        state.queryViewLabel = "ALL"
        refresh_after_variable_catalog_change()

    @state.change("showOnlyVisualizedVars")
    def on_show_only_visualized_vars(showOnlyVisualizedVars, **_):
        refresh_after_variable_catalog_change()

    @state.change("selectedVar")
    def on_selected_var(selectedVar, **_):
        if not selectedVar:
            clear_right_panes(state)
            state.dbOk = db.ok
            state.dbStatus = "Connected" if db.ok else f"DB error: {db.last_error}"
            return
        update_selected_var_panels(selectedVar)

    def ingest_campaign_every_time(**_kwargs):
        if not db.ok:
            state.dbOk = False
            state.dbStatus = f"DB error: {db.last_error}"
            return

        try:
            state.dbOk = True
            schema_note = f" (schema: {image_association_schema_path})" if image_association_schema_path else ""
            state.dbStatus = f"Loading {campaign_path}{schema_note}..."

            collection.drop()
            parse_campaign(
                campaign_path,
                collection,
                image_association_schema_path=image_association_schema_path or None,
            )

            refresh_variable_list()
            state.dbStatus = f"Loaded {campaign_path} • variables={len(state.variableNames)}"
        except Exception as e:
            state.dbOk = False
            state.dbStatus = f"Load failed: {type(e).__name__}: {e}"

    ctrl.on_server_ready.add(ingest_campaign_every_time)

    return refresh_variable_list
