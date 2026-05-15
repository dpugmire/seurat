from typing import Any, Dict, List

from config import MAX_MOVIE_FRAMES, MOVIE_FPS
from query_parser import and_filter, python_query_to_mongo
from state_init import clear_right_panes, fmt


def attach_controllers(
    server,
    db,
    collection,
    parse_campaign,
    campaign_path: str,
    image_association_schema_path: str = "",
):
    state, ctrl = server.state, server.controller
    GRID_CELL_COUNT = 9

    def refresh_variable_list():
        grouped = db.grouped_variable_names(
            extra_filter=state.queryFilter or None,
            only_visualized=bool(state.showOnlyVisualizedVars),
        )
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

    def source_row_keys() -> List[str]:
        return [str(r.get("_key", "")) for r in (state.sourceRows or []) if str(r.get("_key", ""))]

    def update_selected_source_label():
        total = len(state.sourceRows or [])
        selected = len(state.selectedSourceKeys or [])
        if total <= 0:
            state.selectedSourceLabel = "No sources"
        elif selected <= 0:
            state.selectedSourceLabel = "No sources selected"
        elif selected >= total:
            state.selectedSourceLabel = "All sources"
        else:
            state.selectedSourceLabel = f"{selected} of {total} selected"

    def show_all_sources():
        state.selectedSourceKeys = source_row_keys()
        update_selected_source_label()

    def source_filter_from_row(row: Dict[str, str]) -> Dict[str, str]:
        variable_id = str(row.get("variable_id", "") or "")
        if variable_id:
            filt = {"variable_id": variable_id}
            source_dataset = str(row.get("source_dataset", "") or "")
            if source_dataset:
                filt["source_dataset"] = source_dataset
            return filt

        source_dataset = str(row.get("source_dataset", "") or "")
        if source_dataset:
            return {"source_dataset": source_dataset}

        filt: Dict[str, str] = {
            "producer": row.get("producer", ""),
            "casename": row.get("casename", ""),
        }
        file_name = row.get("file", "")
        if file_name:
            filt["file"] = file_name
        return filt

    def empty_grid_cell() -> Dict[str, Any]:
        return {
            "variable_id": "",
            "variable_name": "",
            "visualization_name": "",
            "selected_visualization": "",
            "visualization_options": [],
            "source_dataset": "",
            "producer": "",
            "casename": "",
            "file": "",
            "src": "",
            "media_type": "",
            "status": "empty",
            "note": "",
        }

    def normalize_grid_cells(raw_cells) -> List[Dict[str, Any]]:
        items = list(raw_cells or [])[:GRID_CELL_COUNT]
        cells: List[Dict[str, Any]] = []
        for item in items:
            base = empty_grid_cell()
            if isinstance(item, dict):
                base.update(item)
            cells.append(base)
        while len(cells) < GRID_CELL_COUNT:
            cells.append(empty_grid_cell())
        return cells

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

    def build_grid_cell_for_variable(variable_id: str, preferred_vis: str = "") -> Dict[str, Any]:
        cell = empty_grid_cell()
        var_id = str(variable_id or "").strip()
        if not var_id:
            return cell
        label = variable_label(var_id)

        qf = state.queryFilter or None
        vis_names = db.distinct_visualization_names_for_variable(var_id, extra_filter=qf)

        selected_vis = choose_visualization_default(vis_names, preferred_vis)

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

        if selected_vis:
            movie_query = and_filter(qf, {"visualization_name": selected_vis}) if qf else {"visualization_name": selected_vis}
            one = db.get_first_movie_tiles_for_variable(
                var_id,
                extra_filter=movie_query,
                limit=1,
                limit_frames=MAX_MOVIE_FRAMES,
                fps=MOVIE_FPS,
            )
            if one:
                cell.update(one[0] or {})
            else:
                cell["status"] = "no-frames"
                cell["note"] = f'No movie for "{selected_vis}"'

        cell["variable_id"] = var_id
        cell["variable_name"] = label
        cell["visualization_name"] = selected_vis
        cell["selected_visualization"] = selected_vis
        cell["visualization_options"] = vis_names
        return cell

    def refresh_grid_cells():
        cells = normalize_grid_cells(state.gridCells)
        updated: List[Dict[str, Any]] = []

        for c in cells:
            var_id = str(c.get("variable_id", "") or c.get("variable_name", "") or "").strip()
            if not var_id:
                updated.append(empty_grid_cell())
                continue

            preferred_vis = str(c.get("selected_visualization", "") or "")
            try:
                updated.append(build_grid_cell_for_variable(var_id, preferred_vis=preferred_vis))
            except Exception as e:
                err_cell = empty_grid_cell()
                err_cell["variable_id"] = var_id
                err_cell["variable_name"] = variable_label(var_id)
                err_cell["status"] = "error"
                err_cell["note"] = f"{type(e).__name__}: {e}"
                updated.append(err_cell)

        state.gridCells = updated

        try:
            idx = int(state.activeGridCell)
        except Exception:
            idx = -1
        state.activeGridCell = idx if 0 <= idx < GRID_CELL_COUNT else -1

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

        asc = bool(state.sourceSortAsc)
        rows = list(state.sourceRows or [])
        selected_keys = set(state.selectedSourceKeys or [])

        def keyfn(row: Dict[str, str]):
            if field == "show":
                key = str(row.get("_key", ""))
                # Ascending puts checked sources first.
                return (0 if key in selected_keys else 1, key)

            v = row.get(field, "")
            if v is None:
                return ("__str__", "")
            s = str(v)

            if field in ("min", "max"):
                try:
                    return ("__num__", float(s))
                except Exception:
                    return ("__str__", s.lower())

            return ("__str__", s.lower())

        state.sourceRows = sorted(rows, key=keyfn, reverse=(not asc))

    def refresh_after_variable_catalog_change():
        refresh_variable_list()
        if state.selectedVar and state.selectedVar not in (state.variableNames or []):
            state.selectedVar = ""
            clear_right_panes(state)
        else:
            update_selected_var_panels(state.selectedVar)
        refresh_grid_cells()

    def update_selected_var_panels(variable_id: str):
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
        qf = state.queryFilter or None
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
        state.sourceRows = [
            {
                "source_dataset": r.get("source_dataset", ""),
                "variable_id": r.get("variable_id", ""),
                "variable_path": r.get("variable_path", ""),
                "producer": r.get("producer", ""),
                "casename": r.get("casename", ""),
                "file": r.get("file", ""),
                "min": fmt(r.get("min", None)),
                "max": fmt(r.get("max", None)),
                "_key": (
                    "|".join(
                        str(r.get(key, "") or "")
                        for key in ("variable_id", "source_dataset", "producer", "casename", "file")
                    ).strip("|")
                    or str(r.get("source_dataset", "") or "")
                    or f"{r.get('producer', '')}|{r.get('casename', '')}|{r.get('file', '')}"
                ),
            }
            for r in rows
        ]

        if state.sourceSortField:
            sort_sources(state.sourceSortField, toggle=False)

        all_keys = source_row_keys()
        if previous_var != var_id:
            state.selectedSourceKeys = [all_keys[0]] if all_keys else []
        else:
            selected = set(state.selectedSourceKeys or [])
            state.selectedSourceKeys = [k for k in all_keys if k in selected]
        update_selected_source_label()

        try:
            if all_keys and not state.selectedSourceKeys:
                state.movieTiles = []
                state.movieDetailsOpen = {}
                state.tileVisualizationBySource = {}
                state.movieStatus = "No sources selected"
                return

            selected_set = set(state.selectedSourceKeys or [])
            selected_rows = [r for r in (state.sourceRows or []) if str(r.get("_key", "")) in selected_set]

            tiles: List[Dict[str, str]] = []
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

                tile: Dict[str, str] = {
                    "variable_id": var_id,
                    "variable_name": label,
                    "visualization_name": selected_vis,
                    "source_dataset": row.get("source_dataset", ""),
                    "producer": row.get("producer", ""),
                    "casename": row.get("casename", ""),
                    "file": row.get("file", ""),
                    "src": "",
                    "media_type": "video",
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
        if 0 <= active < GRID_CELL_COUNT:
            if not str(cells[active].get("variable_id", "") or cells[active].get("variable_name", "") or "").strip():
                target = active

        if target < 0:
            for i, c in enumerate(cells):
                if not str(c.get("variable_id", "") or c.get("variable_name", "") or "").strip():
                    target = i
                    break

        if target < 0:
            target = active if 0 <= active < GRID_CELL_COUNT else 0

        try:
            cells[target] = build_grid_cell_for_variable(var)
        except Exception as e:
            err_cell = empty_grid_cell()
            err_cell["variable_id"] = var
            err_cell["variable_name"] = variable_label(var)
            err_cell["status"] = "error"
            err_cell["note"] = f"{type(e).__name__}: {e}"
            cells[target] = err_cell

        state.gridCells = cells
        state.activeGridCell = target
        state.selectedVar = var
        state.draggedVar = var

    @ctrl.add("set_active_grid_cell")
    def set_active_grid_cell(cell_index: int, ignore=0, **_):
        try:
            if int(ignore):
                return
        except Exception:
            pass

        try:
            idx = int(cell_index)
        except Exception:
            return
        if idx < 0 or idx >= GRID_CELL_COUNT:
            return

        state.activeGridCell = idx
        cells = normalize_grid_cells(state.gridCells)
        var = str(cells[idx].get("variable_id", "") or cells[idx].get("variable_name", "") or "")
        if var:
            state.selectedVar = var
            state.draggedVar = var
            return

        selected = str(state.selectedVar or "").strip()
        if not selected:
            return

        try:
            cells[idx] = build_grid_cell_for_variable(selected)
        except Exception as e:
            err_cell = empty_grid_cell()
            err_cell["variable_id"] = selected
            err_cell["variable_name"] = variable_label(selected)
            err_cell["status"] = "error"
            err_cell["note"] = f"{type(e).__name__}: {e}"
            cells[idx] = err_cell
        state.gridCells = cells

    @ctrl.add("clear_grid_cell")
    def clear_grid_cell(cell_index: int, **_):
        try:
            idx = int(cell_index)
        except Exception:
            return
        if idx < 0 or idx >= GRID_CELL_COUNT:
            return

        cells = normalize_grid_cells(state.gridCells)
        cells[idx] = empty_grid_cell()
        state.gridCells = cells

    @ctrl.add("move_grid_cell")
    def move_grid_cell(from_index: int, to_index: int, **_):
        try:
            src = int(from_index)
            dst = int(to_index)
        except Exception:
            return
        if src < 0 or src >= GRID_CELL_COUNT or dst < 0 or dst >= GRID_CELL_COUNT:
            return
        if src == dst:
            return

        cells = normalize_grid_cells(state.gridCells)
        source = dict(cells[src] or {})
        if not str(source.get("variable_id", "") or source.get("variable_name", "") or "").strip():
            return

        # Move + overwrite: destination takes source tile, source is cleared.
        cells[dst] = source
        cells[src] = empty_grid_cell()
        state.gridCells = cells
        state.activeGridCell = dst

    @ctrl.trigger("move_grid_cell_trigger")
    def move_grid_cell_trigger(from_index, to_index, **_):
        move_grid_cell(from_index, to_index)

    @ctrl.add("assign_var_to_grid_cell")
    def assign_var_to_grid_cell(cell_index: int, var_name: str, sync_selection: bool = True, **_):
        try:
            idx = int(cell_index)
        except Exception:
            return
        if idx < 0 or idx >= GRID_CELL_COUNT:
            return

        var = str(var_name or "").strip()
        if not var:
            var = str(state.draggedVar or "").strip()
        if not var:
            var = str(state.selectedVar or "").strip()
        if not var:
            return

        cells = normalize_grid_cells(state.gridCells)
        try:
            cells[idx] = build_grid_cell_for_variable(var)
        except Exception as e:
            err_cell = empty_grid_cell()
            err_cell["variable_id"] = var
            err_cell["variable_name"] = variable_label(var)
            err_cell["status"] = "error"
            err_cell["note"] = f"{type(e).__name__}: {e}"
            cells[idx] = err_cell
        state.gridCells = cells
        state.activeGridCell = idx
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
        if idx < 0 or idx >= GRID_CELL_COUNT:
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
            cells[idx] = build_grid_cell_for_variable(var, preferred_vis=picked)
        except Exception as e:
            err_cell = empty_grid_cell()
            err_cell["variable_id"] = var
            err_cell["variable_name"] = variable_label(var)
            err_cell["status"] = "error"
            err_cell["note"] = f"{type(e).__name__}: {e}"
            cells[idx] = err_cell

        state.gridCells = cells
        state.activeGridCell = idx
        state.selectedVar = var

    @ctrl.add("hide_context_menu")
    def hide_context_menu(**_):
        state.contextMenuVisible = False
        state.contextMenuKind = ""
        state.contextMenuItem = ""
        state.contextMenuItemLabel = ""
        state.contextMenuCellIndex = -1
        state.contextMenuCellVisualizationOptions = []
        state.contextMenuCellSelectedVisualization = ""

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
        state.contextMenuCellVisualizationOptions = []
        state.contextMenuCellSelectedVisualization = ""
        state.contextMenuX = px
        state.contextMenuY = py
        state.contextMenuVisible = True

    @ctrl.trigger("show_cell_context_menu")
    def show_cell_context_menu(cell_index, x, y, **_):
        try:
            idx = int(cell_index)
        except Exception:
            return
        if idx < 0 or idx >= GRID_CELL_COUNT:
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
        label = str(cell.get("variable_name", "") or "").strip() or f"Cell {idx + 1}"
        vis_opts = []
        for raw_vis in (cell.get("visualization_options", []) or []):
            vis = str(raw_vis or "").strip()
            if vis and vis not in vis_opts:
                vis_opts.append(vis)
        selected_vis = str(cell.get("selected_visualization", "") or cell.get("visualization_name", "") or "").strip()
        if selected_vis and selected_vis not in vis_opts:
            vis_opts.append(selected_vis)

        state.contextMenuKind = "cell"
        state.contextMenuItem = label
        state.contextMenuItemLabel = label
        state.contextMenuCellIndex = idx
        state.contextMenuCellVisualizationOptions = vis_opts
        state.contextMenuCellSelectedVisualization = selected_vis
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
        if 0 <= idx < GRID_CELL_COUNT:
            clear_grid_cell(idx)
        hide_context_menu()

    @ctrl.add("context_menu_cell_select")
    def context_menu_cell_select(**_):
        try:
            idx = int(state.contextMenuCellIndex)
        except Exception:
            idx = -1
        if 0 <= idx < GRID_CELL_COUNT:
            set_active_grid_cell(idx, 0)
        hide_context_menu()

    @ctrl.add("context_menu_cell_pick_visualization")
    def context_menu_cell_pick_visualization(value: str = "", **_):
        try:
            idx = int(state.contextMenuCellIndex)
        except Exception:
            idx = -1
        if idx < 0 or idx >= GRID_CELL_COUNT:
            hide_context_menu()
            return

        picked = str(value or "").strip()
        if not picked:
            hide_context_menu()
            return

        pick_grid_cell_visualization(idx, picked)
        hide_context_menu()

    @ctrl.add("toggle_sources")
    def toggle_sources(**_):
        state.showSourcesModal = not bool(state.showSourcesModal)

    @ctrl.add("clear_source_filter")
    def clear_source_filter(**_):
        show_all_sources()
        update_selected_var_panels(state.selectedVar)

    @ctrl.add("toggle_source_visibility")
    def toggle_source_visibility(key: str, **_):
        k = str(key or "")
        if not k:
            return

        selected = set(state.selectedSourceKeys or [])
        if k in selected:
            selected.remove(k)
        else:
            selected.add(k)
        state.selectedSourceKeys = [key for key in source_row_keys() if key in selected]
        update_selected_source_label()

        state.showSourcesModal = True
        update_selected_var_panels(state.selectedVar)

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
            state.queryError = ""
            state.queryStatus = "Query cleared"
            state.queryViewLabel = "ALL"
            refresh_after_variable_catalog_change()
            return

        try:
            filt = python_query_to_mongo(q)
            state.queryFilter = filt
            state.queryError = ""
            state.queryStatus = "Query OK"
            state.queryViewLabel = q
        except Exception as e:
            state.queryFilter = {}
            state.queryError = f"{type(e).__name__}: {e}"
            state.queryStatus = "Query ERROR"
            state.queryViewLabel = "ALL"
            return

        refresh_after_variable_catalog_change()

    @ctrl.add("clear_query")
    def clear_query(**_):
        state.queryText = ""
        state.queryFilter = {}
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
