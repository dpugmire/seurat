"""Catalog, query, and variable-selection controller behavior."""

from typing import Any, Dict, List, Optional

from application import NavigationNode
from config import MAX_MOVIE_FRAMES, MOVIE_FPS
from query_parser import and_filter, python_query_to_filters
from seurat.models.source_selection import (
    normalize_source_keys,
    source_fields_from_row,
    source_filter_from_row,
)
from seurat.state import clear_right_panes
from state_init import fmt


def _variable_groups_from_navigation(
    nodes: List[NavigationNode],
) -> List[Dict[str, Any]]:
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
            group: Dict[str, Any] = {
                "name": str(node.get("label", "") or ""),
                "variables": variables,
            }
            resource = node.get("resource") or {}
            file_count = int(resource.get("file_count", 0) or 0)
            if file_count > 1:
                group["file_count"] = file_count
            groups.append(group)
    return groups


def _filter_variable_groups(
    groups: List[Dict[str, Any]],
    search_text: Any,
) -> List[Dict[str, Any]]:
    """Filter catalog groups locally without changing the canonical catalog."""

    needle = str(search_text or "").strip().casefold()
    if not needle:
        return list(groups or [])

    filtered: List[Dict[str, Any]] = []
    variable_fields = (
        "id",
        "name",
        "label",
        "path",
        "source_dataset",
    )
    for raw_group in groups or []:
        if not isinstance(raw_group, dict):
            continue
        group = dict(raw_group)
        variables = [
            variable
            for variable in (raw_group.get("variables", []) or [])
            if isinstance(variable, dict)
        ]
        group_matches = needle in str(
            raw_group.get("name", "") or ""
        ).casefold()
        if group_matches:
            matches = variables
        else:
            matches = [
                variable
                for variable in variables
                if any(
                    needle in str(variable.get(field, "") or "").casefold()
                    for field in variable_fields
                )
            ]
        if matches:
            group["variables"] = matches
            filtered.append(group)
    return filtered


def _display_representation_summary(raw: Any) -> Dict[str, Any]:
    representation = dict(raw or {}) if isinstance(raw, dict) else {}
    return {
        "id": str(representation.get("id", "") or ""),
        "label": str(representation.get("label", "") or ""),
        "kind": str(representation.get("kind", "") or ""),
        "data_model": str(representation.get("data_model", "") or ""),
        "source_data_model": str(
            representation.get("source_data_model", "") or ""
        ),
        "shape": str(representation.get("shape", "") or ""),
        "axes": str(representation.get("axes", "") or ""),
        "num_frames": int(representation.get("num_frames", 0) or 0),
        "num_sources": int(representation.get("num_sources", 0) or 0),
        "global_min": fmt(representation.get("global_min", None)),
        "global_max": fmt(representation.get("global_max", None)),
        "mean_min": fmt(representation.get("mean_min", None)),
        "mean_max": fmt(representation.get("mean_max", None)),
        "median_min": fmt(representation.get("median_min", None)),
        "median_max": fmt(representation.get("median_max", None)),
    }


def _text(value: Any) -> str:
    return str(value or "").strip()


def _first_text(item: Dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = _text(item.get(key, ""))
        if value:
            return value
    return ""


def _source_label_for_provenance(row: Dict[str, Any]) -> str:
    label = _first_text(
        row,
        "sourceName",
        "source_label",
        "schema_file_group",
        "source_dataset",
    )
    if label:
        return label
    return "/".join(
        part
        for part in (
            _text(row.get("producer", "")),
            _text(row.get("casename", "")),
            _text(row.get("file", "")),
        )
        if part
    )


def _dict_value(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_value(value: Any) -> List[Any]:
    return list(value) if isinstance(value, list) else []


def _short_variable_name(value: Any) -> str:
    name = _text(value).strip("/")
    if "/" in name:
        return name.rsplit("/", 1)[-1]
    return name


def _input_roles(item: Dict[str, Any]) -> List[str]:
    roles = item.get("roles", [])
    if isinstance(roles, list):
        return [_text(role).lower() for role in roles if _text(role)]
    role = _text(item.get("role", "")).lower()
    return [role] if role else []


def _role_priority(role: str) -> tuple[int, int]:
    normalized = _text(role).lower().replace("-", "_")
    if normalized.startswith("streamline_"):
        suffix = normalized.rsplit("_", 1)[-1]
        try:
            return (0, int(suffix))
        except Exception:
            return (0, 0)
    if normalized in {"streamline", "streamline_by"}:
        return (0, 0)
    if normalized in {"color", "color_by"}:
        return (20, 0)
    if normalized in {"contour", "contour_by"}:
        return (30, 0)
    if normalized.startswith("y_axis"):
        return (40, 0)
    if normalized in {"primary", "variable", "source"}:
        return (50, 0)
    if normalized in {"x_axis"}:
        return (90, 0)
    return (60, 0)


def _skip_input(roles: List[str]) -> bool:
    normalized = {_text(role).lower().replace("-", "_") for role in roles}
    return bool(normalized) and normalized <= {"x_axis"}


def _provenance_input_names(raw_inputs: Any) -> List[str]:
    inputs = _list_value(raw_inputs)
    items: List[Dict[str, Any]] = []
    for index, raw in enumerate(inputs):
        if isinstance(raw, str):
            raw = {"name": raw, "roles": ["source"]}
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        roles = _input_roles(item)
        if _skip_input(roles):
            continue
        name = _short_variable_name(
            _first_text(item, "label", "name", "variable_name", "variable_id", "definition")
        )
        if not name:
            continue
        priority = min((_role_priority(role) for role in roles), default=(60, index))
        item["_display_name"] = name
        item["_priority"] = priority
        item["_index"] = index
        items.append(item)

    items.sort(
        key=lambda item: (
            item.get("_priority", (60, 0)),
            int(item.get("_index", 0) or 0),
            str(item.get("_display_name", "")),
        )
    )
    names: List[str] = []
    seen = set()
    for item in items:
        name = str(item.get("_display_name", "") or "")
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        names.append(name)
    return names


def _activity_label(kind: Any, operation: Any = "") -> str:
    raw_kind = _text(kind)
    kind_norm = raw_kind.lower()
    op = _text(operation)
    if kind_norm == "quantity_of_interest":
        label = "statistics" if op == "descriptive_statistics" else "derived"
    elif kind_norm:
        label = raw_kind
    else:
        label = "activity"

    if op and op.casefold() != label.casefold():
        return f"{label}: {op}"
    return label


def _visualization_operation(tile: Dict[str, Any], row: Dict[str, Any]) -> str:
    sequence_metadata = _dict_value(
        tile.get("visualization_sequence_metadata")
        or row.get("visualization_sequence_metadata")
    )
    item_metadata = _dict_value(
        tile.get("visualization_item_metadata")
        or row.get("visualization_item_metadata")
    )
    for item in (sequence_metadata, item_metadata, tile, row):
        value = _first_text(
            item,
            "visualization_type",
            "operation",
            "visualization_kind",
            "representation_kind",
            "payload_type",
            "visualization_item_type",
            "kind",
        )
        if value:
            return value
    return ""


def _chain(*parts: Any) -> str:
    return " --> ".join(_text(part) for part in parts if _text(part))


def _details_provenance_summary(
    variable_label: str,
    selected_rows: List[Dict[str, Any]],
    tiles: List[Dict[str, Any]],
    include_visualization: bool = False,
) -> Dict[str, Any]:
    label = _text(variable_label)
    rows = [dict(row or {}) for row in selected_rows or [] if isinstance(row, dict)]
    if not label or not rows:
        return {"kind": "", "chain": ""}

    if len(rows) > 1:
        count = len(rows)
        return {
            "kind": "multiple_sources",
            "chain": f"{label} --> {count} selected sources",
        }

    row = rows[0]
    tile = dict(tiles[0] or {}) if tiles else {}
    variable_name = label or _first_text(row, "variable_name", "variable_id")
    source_label = _source_label_for_provenance(row) or "source"
    visualization_name = ""
    if include_visualization:
        visualization_name = _first_text(
            tile,
            "selected_visualization",
            "visualization_name",
        )
        if not visualization_name:
            visualization_name = _first_text(row, "visualization_name")

    if visualization_name:
        activity = _activity_label("visualization", _visualization_operation(tile, row))
        inputs = _provenance_input_names(
            tile.get("visualization_variables")
            or row.get("visualization_variables")
            or []
        )
        input_label = " + ".join(inputs) if inputs else variable_name
        chain = _chain(visualization_name, activity, input_label, source_label)
        return {"kind": "visualization", "chain": chain}

    activity_provenance = _dict_value(row.get("activity_provenance", {}))
    if activity_provenance:
        activity = _activity_label(
            activity_provenance.get("activity_kind", ""),
            activity_provenance.get("activity_operation", ""),
        )
        inputs = _provenance_input_names(activity_provenance.get("inputs", []))
        if inputs:
            chain = _chain(variable_name, activity, " + ".join(inputs), source_label)
        else:
            chain = _chain(variable_name, activity, source_label)
        return {"kind": "activity", "chain": chain}

    chain = _chain(variable_name, source_label)
    kind = "variable"

    return {"kind": kind, "chain": chain}


class CatalogControllerMixin:
    ACTION_BINDINGS = (
        ("pick_var", "pick_var"),
        ("select_var", "select_var"),
        ("set_dragged_var", "set_dragged_var"),
        ("toggle_variable_group", "toggle_variable_group"),
        ("show_query_help", "show_query_help"),
        ("show_source_filter_help", "show_source_filter_help"),
        ("close_help_modal", "close_help_modal"),
        ("run_query", "run_query"),
        ("clear_query", "clear_query"),
    )
    TRIGGER_BINDINGS = ()
    STATE_CHANGE_BINDINGS = (
        (("showOnlyVisualizedVars",), "on_show_only_visualized_vars"),
        (("variablePaneView",), "on_variable_pane_view"),
        (("variableSearchText",), "on_variable_search_text"),
        (("selectedVar",), "on_selected_var"),
    )

    def active_query_filter(self) -> Optional[Dict[str, Any]]:
        query_filter = self.state.queryFilter or None
        source_restriction = self.state.querySourceRestrictionFilter or None
        if query_filter and source_restriction:
            return and_filter(query_filter, source_restriction)
        return query_filter or source_restriction or None

    @staticmethod
    def combined_query_filter(
        query_filter: Dict[str, Any],
        source_restriction: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        if query_filter and source_restriction:
            return and_filter(query_filter, source_restriction)
        return query_filter or source_restriction or None

    def variable_pane_view(self) -> str:
        view = str(getattr(self.state, "variablePaneView", "variables") or "variables")
        return "files" if view == "files" else "variables"

    def refresh_variable_list(self):
        view = self.variable_pane_view()
        navigation = self.application.get_navigation(
            {
                "view": view,
                "query": self.active_query_filter() or {},
                "only_visualized": bool(self.state.showOnlyVisualizedVars),
                "parent_id": None,
            }
        )
        grouped = _variable_groups_from_navigation(navigation)
        self.state.variableGroups = grouped
        self.update_variable_search_results()
        variables = [
            variable
            for group in grouped
            for variable in (group.get("variables") or [])
            if isinstance(variable, dict)
        ]
        self.state.variableNames = list(
            dict.fromkeys(
                str(v.get("id", "") or "")
                for v in variables
                if str(v.get("id", "") or "")
            )
        )
        self.state.variableLabelsById = {
            str(v.get("id", "") or ""): str(
                v.get("label", "") or v.get("name", "") or v.get("id", "") or ""
            )
            for v in variables
            if str(v.get("id", "") or "")
        }
        collapsed_by_view = dict(
            getattr(self.state, "variableGroupCollapsedByView", {}) or {}
        )
        existing_collapsed = dict(collapsed_by_view.get(view, {}) or {})
        valid_group_names = {str(g.get("name", "")) for g in grouped}
        self.state.variableGroupCollapsed = {
            name: bool(existing_collapsed.get(name, True))
            for name in valid_group_names
            if name
        }
        collapsed_by_view[view] = dict(self.state.variableGroupCollapsed)
        self.state.variableGroupCollapsedByView = collapsed_by_view
        backend_status = self.application.get_backend_status()
        self.state.dbOk = backend_status.ok
        self.state.dbStatus = (
            "Connected"
            if backend_status.ok
            else f"DB error: {backend_status.error}"
        )

    def update_variable_search_results(self) -> None:
        search_text = str(
            getattr(self.state, "variableSearchText", "") or ""
        ).strip()
        self.state.filteredVariableGroups = (
            _filter_variable_groups(
                list(self.state.variableGroups or []),
                search_text,
            )
            if search_text
            else []
        )

    def show_help(self, title: str) -> None:
        self.state.helpModalTitle = title
        if str(title or "") in {"Query Help", "Source Filter Help"}:
            scope_note = (
                "Query applies globally to the variable list, source lists, grid cells, and generated plots."
                if str(title or "") == "Query Help"
                else "Source Filter applies only to source rows that already passed the active Query."
            )
            self.state.helpModalText = f"""Use Python-like expressions to filter variables and sources.

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
            self.state.helpModalText = "TODO"
        self.state.showHelpModal = True

    def refresh_after_variable_catalog_change(self):
        self.refresh_variable_list()
        if self.state.selectedVar and self.state.selectedVar not in (
            self.state.variableNames or []
        ):
            self.state.selectedVar = ""
            clear_right_panes(self.state)
        else:
            self.update_selected_var_panels(
                self.state.selectedVar,
                include_visualization_provenance=(
                    self.details_provenance_includes_visualization()
                ),
            )
        self.refresh_grid_cells()

    def update_selected_var_panels(
        self,
        variable_id: str,
        preferred_source_key: str = "",
        preferred_source_keys: Optional[List[str]] = None,
        include_visualization_provenance: bool = False,
        preferred_visualization: str = "",
    ):
        var_id = str(variable_id or "").strip()
        if not var_id:
            clear_right_panes(self.state)
            return

        label = self.variable_label(var_id)
        previous_var = self.state.detailsSelectedVarId
        previous_tile_map = (
            dict(self.state.tileVisualizationBySource or {})
            if previous_var == var_id
            else {}
        )
        qf = self.active_query_filter()
        preferred_vis = str(preferred_visualization or "").strip()
        summary = self.application.get_source_summary(
            {"variable_id": var_id, "query": qf or {}}
        )

        backend_status = self.application.get_backend_status()
        self.state.dbOk = backend_status.ok
        self.state.dbStatus = (
            f'Connected • Selected variable: "{label}" • QueryView: {self.state.queryViewLabel}'
            if backend_status.ok
            else f'DB error • "{label}" • {backend_status.error}'
        )

        self.state.detailsSelectedVar = label
        self.state.detailsSelectedVarId = var_id
        self.state.detailsNumSources = int(summary.get("num_sources", 0))

        self.state.detailsGlobalMin = fmt(summary.get("global_min", None))
        self.state.detailsGlobalMax = fmt(summary.get("global_max", None))
        self.state.detailsMeanMin = fmt(summary.get("mean_min", None))
        self.state.detailsMeanMax = fmt(summary.get("mean_max", None))
        self.state.detailsMedianMin = fmt(summary.get("median_min", None))
        self.state.detailsMedianMax = fmt(summary.get("median_max", None))
        self.state.detailsSourceRepresentation = _display_representation_summary(
            summary.get("source_representation", {})
        )
        self.state.detailsDerivedRepresentations = [
            _display_representation_summary(representation)
            for representation in summary.get("derived_representations", []) or []
            if isinstance(representation, dict)
        ]

        rows = summary.get("sources", []) or []
        source_rows_all: List[Dict[str, Any]] = []
        for r in rows:
            source_rows_all.append(
                self.source_row_from_descriptor(dict(r or {}), var_id)
            )

        self.state.sourceRowsAll = source_rows_all
        self.apply_source_filter_and_sort()

        all_keys = self.source_row_keys()
        allow_multi_sources = str(self.state.sourceDialogMode or "single") == "add"
        preferred_keys = [
            key
            for key in normalize_source_keys(preferred_source_keys or [])
            if key in all_keys
        ]
        preferred_key = str(preferred_source_key or "")
        if preferred_keys:
            self.state.selectedSourceKeys = (
                preferred_keys if allow_multi_sources else preferred_keys[:1]
            )
        elif preferred_key and preferred_key in all_keys:
            self.state.selectedSourceKeys = [preferred_key]
        elif previous_var != var_id:
            self.state.selectedSourceKeys = [all_keys[0]] if all_keys else []
        else:
            selected = set(self.state.selectedSourceKeys or [])
            selected_keys = [k for k in all_keys if k in selected]
            if allow_multi_sources:
                self.state.selectedSourceKeys = selected_keys or (
                    [all_keys[0]] if all_keys else []
                )
            else:
                self.state.selectedSourceKeys = selected_keys[:1] or (
                    [all_keys[0]] if all_keys else []
                )
        self.update_selected_source_label()

        selected_rows: List[Dict[str, Any]] = []
        try:
            if all_keys and not self.state.selectedSourceKeys:
                self.state.movieTiles = []
                self.state.movieDetailsOpen = {}
                self.state.tileVisualizationBySource = {}
                self.state.movieStatus = "No sources selected"
                self.update_details_provenance(
                    label,
                    selected_rows,
                    [],
                    include_visualization=include_visualization_provenance,
                )
                return

            selected_rows = self.source_rows_for_keys(
                normalize_source_keys(self.state.selectedSourceKeys or [])
            )

            tiles: List[Dict[str, Any]] = []
            new_tile_map: Dict[str, str] = {}

            for row in selected_rows:
                source_key = str(row.get("_key", ""))
                source_filter = source_filter_from_row(row)
                source_query = and_filter(qf, source_filter) if qf else source_filter

                vis_names = self.db.distinct_visualization_names_for_variable(
                    var_id,
                    extra_filter=source_query,
                )
                selected_vis = self.choose_visualization_default(
                    vis_names, preferred_vis or previous_tile_map.get(source_key, "")
                )
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
                    movie_query = and_filter(
                        source_query, {"visualization_name": selected_vis}
                    )
                    one = self.db.get_first_movie_tiles_for_variable(
                        var_id,
                        extra_filter=movie_query,
                        limit=1,
                        limit_frames=MAX_MOVIE_FRAMES,
                        fps=MOVIE_FPS,
                    )
                    if one:
                        tile = one[0]
                        tile.update(
                            {k: v for k, v in source_fields_from_row(row).items() if v}
                        )
                    else:
                        tile["status"] = "no-frames"
                        tile["note"] = f'No movie for "{selected_vis}"'

                tile["_source_key"] = source_key
                tile["variable_id"] = var_id
                tile["variable_name"] = label
                tile["visualization_options"] = vis_names
                tile["selected_visualization"] = selected_vis
                tiles.append(tile)

            self.state.tileVisualizationBySource = new_tile_map
            self.state.movieTiles = tiles
            self.state.movieDetailsOpen = {}
            self.state.movieStatus = ""
            if self.state.movieTiles:
                with_media = sum(1 for t in self.state.movieTiles if t.get("src"))
                self.state.movieStatus = (
                    f"{with_media}/{len(self.state.movieTiles)} sources with media"
                )
            self.update_details_provenance(
                label,
                selected_rows,
                tiles,
                include_visualization=include_visualization_provenance,
            )
        except Exception as e:
            self.state.movieTiles = []
            self.state.movieDetailsOpen = {}
            self.state.tileVisualizationBySource = {}
            self.state.movieStatus = (
                f"Movie query/build failed: {type(e).__name__}: {e}"
            )
            self.update_details_provenance(
                label,
                selected_rows,
                [],
                include_visualization=include_visualization_provenance,
            )

    def update_details_provenance(
        self,
        variable_label: str,
        selected_rows: List[Dict[str, Any]],
        tiles: List[Dict[str, Any]],
        include_visualization: bool = False,
    ) -> None:
        self.state.detailsProvenanceContext = (
            "visualization" if include_visualization else "variable"
        )
        provenance = _details_provenance_summary(
            variable_label,
            selected_rows,
            tiles,
            include_visualization=include_visualization,
        )
        self.state.detailsProvenanceKind = str(provenance.get("kind", "") or "")
        self.state.detailsProvenanceChain = str(provenance.get("chain", "") or "")

    def details_provenance_includes_visualization(self) -> bool:
        return (
            str(getattr(self.state, "detailsProvenanceContext", "") or "variable")
            == "visualization"
        )

    def set_details_provenance_context(
        self, include_visualization: bool = False
    ) -> None:
        self.state.detailsProvenanceContext = (
            "visualization" if include_visualization else "variable"
        )

    def pick_var(self, var_name: str, **_):
        picked = str(var_name or "")
        self.set_details_provenance_context(False)
        if str(self.state.selectedVar or "") == picked:
            self.state.selectedVar = ""
            self.state.draggedVar = ""
        else:
            self.state.selectedVar = picked
            self.state.draggedVar = picked

    def select_var(self, var_name: str, button=0, **_):
        try:
            if int(button) == 2:
                return
        except Exception:
            pass

        picked = str(var_name or "")
        if not picked:
            return
        self.set_details_provenance_context(False)
        self.state.selectedVar = picked
        self.state.draggedVar = picked

    def set_dragged_var(self, var_name: str, **_):
        self.state.draggedVar = str(var_name or "")

    def toggle_variable_group(self, group_name: str, **_):
        name = str(group_name or "").strip()
        if not name:
            return
        collapsed = dict(self.state.variableGroupCollapsed or {})
        collapsed[name] = not bool(collapsed.get(name, False))
        self.state.variableGroupCollapsed = collapsed
        collapsed_by_view = dict(
            getattr(self.state, "variableGroupCollapsedByView", {}) or {}
        )
        collapsed_by_view[self.variable_pane_view()] = dict(collapsed)
        self.state.variableGroupCollapsedByView = collapsed_by_view

    def show_query_help(self, **_):
        self.show_help("Query Help")

    def show_source_filter_help(self, **_):
        self.show_help("Source Filter Help")

    def close_help_modal(self, **_):
        self.state.showHelpModal = False

    def update_query_state(self) -> bool:
        q = (self.state.queryText or "").strip()

        if not q:
            self.state.queryFilter = {}
            self.state.querySourceFilters = []
            self.state.querySourceRestrictionFilter = {}
            self.state.querySourceRestrictionCount = 0
            self.state.queryError = ""
            self.state.queryStatus = "Query cleared"
            self.state.queryViewLabel = "ALL"
            return True

        try:
            evaluation = self.evaluate_query_text(q)
            self.state.queryFilter = evaluation["query_filter"]
            self.state.querySourceFilters = evaluation["source_filters"]
            self.state.querySourceRestrictionFilter = evaluation[
                "source_restriction"
            ]
            self.state.querySourceRestrictionCount = evaluation["source_count"]
            self.state.queryError = ""
            self.state.queryStatus = (
                f"Query OK · {evaluation['source_count']} source "
                f"run{'s' if evaluation['source_count'] != 1 else ''}"
                if evaluation["source_filters"]
                else "Query OK"
            )
            self.state.queryViewLabel = q
        except Exception as e:
            self.state.queryError = f"{type(e).__name__}: {e}"
            self.state.queryStatus = "Query ERROR · active query unchanged"
            return False

        return True

    def evaluate_query_text(self, query_text: str) -> Dict[str, Any]:
        q = str(query_text or "").strip()
        if not q:
            return {
                "query_filter": {},
                "source_filters": [],
                "source_restriction": {},
                "source_count": 0,
                "variable_count": 0,
            }

        query_filter, source_filters = python_query_to_filters(q)
        source_restriction: Dict[str, Any] = {}
        source_count = 0
        if source_filters:
            source_summary = self.application.resolve_source_restriction(
                {"queries": source_filters}
            )
            source_restriction = dict(source_summary.get("query", {}) or {})
            source_count = int(source_summary.get("count", 0) or 0)

        active_filter = self.combined_query_filter(
            query_filter,
            source_restriction,
        )
        navigation = self.application.get_navigation(
            {
                "view": self.variable_pane_view(),
                "query": active_filter or {},
                "only_visualized": bool(self.state.showOnlyVisualizedVars),
                "parent_id": None,
            }
        )
        variable_ids = {
            str((child.get("resource") or {}).get("variable_id", "") or "")
            for node in navigation
            for child in (node.get("children", []) or [])
            if child.get("kind") == "variable"
        }
        variable_ids.discard("")
        return {
            "query_filter": query_filter,
            "source_filters": source_filters,
            "source_restriction": source_restriction,
            "source_count": source_count,
            "variable_count": len(variable_ids),
        }

    def run_query(self, **_):
        if self.update_query_state():
            pending_plan = getattr(
                self, "_interaction_pending_query_action_plan", None
            )
            pending_origin = str(
                getattr(self, "_interaction_pending_query_origin", "manual")
                or "manual"
            )
            self.state.activeViewerActionPlan = {}
            self.state.activeNaturalLanguageQuery = ""
            self.refresh_after_variable_catalog_change()
            if str(self.state.queryText or "").strip():
                self.record_query_applied(
                    origin=pending_origin,
                    target="catalog",
                    action_plan=pending_plan,
                )
            return True
        return False

    def clear_query(self, **_):
        previous_query_id = self._interaction_query_id
        had_query = bool(str(self.state.queryText or "").strip())
        self.state.activeViewerActionPlan = {}
        self.state.activeNaturalLanguageQuery = ""
        self.state.queryText = ""
        self.update_query_state()
        self.refresh_after_variable_catalog_change()
        if had_query or previous_query_id:
            self.record_interaction(
                "query.cleared",
                source="query_toolbar",
                payload={"query_id": previous_query_id, "target": "catalog"},
            )
        self._interaction_query_id = ""

    def on_show_only_visualized_vars(self, showOnlyVisualizedVars, **_):
        self.refresh_after_variable_catalog_change()

    def on_variable_pane_view(self, variablePaneView, **_):
        self.refresh_variable_list()

    def on_variable_search_text(self, variableSearchText, **_):
        self.update_variable_search_results()

    def on_selected_var(self, selectedVar, **_):
        if not selectedVar:
            clear_right_panes(self.state)
            backend_status = self.application.get_backend_status()
            self.state.dbOk = backend_status.ok
            self.state.dbStatus = (
                "Connected"
                if backend_status.ok
                else f"DB error: {backend_status.error}"
            )
            return
        self.update_selected_var_panels(
            selectedVar,
            include_visualization_provenance=(
                self.details_provenance_includes_visualization()
            ),
        )
