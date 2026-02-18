from typing import Dict, List

from config import MAX_MOVIE_FRAMES, MOVIE_FPS
from query_parser import and_filter, python_query_to_mongo
from state_init import clear_right_panes, fmt


def attach_controllers(server, db, collection, parse_campaign, campaign_path: str):
    state, ctrl = server.state, server.controller

    def refresh_variable_list():
        state.variableNames = db.distinct_variable_names(extra_filter=state.queryFilter or None)
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
        filt: Dict[str, str] = {
            "producer": row.get("producer", ""),
            "casename": row.get("casename", ""),
        }
        file_name = row.get("file", "")
        if file_name:
            filt["file"] = file_name
        return filt

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

    def update_selected_var_panels(var_name: str):
        if not var_name:
            clear_right_panes(state)
            return

        previous_var = state.detailsSelectedVar
        previous_tile_map = (
            dict(state.tileVisualizationBySource or {})
            if previous_var == var_name
            else {}
        )
        qf = state.queryFilter or None
        summary = db.variable_min_max_summary(var_name, extra_filter=qf)

        state.dbOk = db.ok
        state.dbStatus = (
            f'Connected • Selected variable: "{var_name}" • QueryView: {state.queryViewLabel}'
            if db.ok
            else f'DB error • "{var_name}" • {db.last_error}'
        )

        state.detailsSelectedVar = var_name
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
                "producer": r.get("producer", ""),
                "casename": r.get("casename", ""),
                "file": r.get("file", ""),
                "min": fmt(r.get("min", None)),
                "max": fmt(r.get("max", None)),
                "_key": f"{r.get('producer', '')}|{r.get('casename', '')}|{r.get('file', '')}",
            }
            for r in rows
        ]

        if state.sourceSortField:
            sort_sources(state.sourceSortField, toggle=False)

        all_keys = source_row_keys()
        if previous_var != var_name:
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
                    var_name,
                    extra_filter=source_query,
                )
                selected_vis = str(previous_tile_map.get(source_key, "") or "")
                if selected_vis not in vis_names:
                    selected_vis = vis_names[0] if vis_names else ""
                if selected_vis:
                    new_tile_map[source_key] = selected_vis

                tile: Dict[str, str] = {
                    "variable_name": var_name,
                    "visualization_name": selected_vis,
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
                        var_name,
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
        state.selectedVar = var_name

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
            refresh_variable_list()

            if state.selectedVar and state.selectedVar not in (state.variableNames or []):
                state.selectedVar = ""
                clear_right_panes(state)
            else:
                update_selected_var_panels(state.selectedVar)
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

        refresh_variable_list()

        if state.selectedVar and state.selectedVar not in (state.variableNames or []):
            state.selectedVar = ""
            clear_right_panes(state)
        else:
            update_selected_var_panels(state.selectedVar)

    @ctrl.add("clear_query")
    def clear_query(**_):
        state.queryText = ""
        state.queryFilter = {}
        state.queryError = ""
        state.queryStatus = "Query cleared"
        state.queryViewLabel = "ALL"
        refresh_variable_list()

        if state.selectedVar and state.selectedVar not in (state.variableNames or []):
            state.selectedVar = ""
            clear_right_panes(state)
        else:
            update_selected_var_panels(state.selectedVar)

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
            state.dbStatus = f"Loading {campaign_path}..."

            collection.drop()
            parse_campaign(campaign_path, collection)

            refresh_variable_list()
            state.dbStatus = f"Loaded {campaign_path} • variables={len(state.variableNames)}"
        except Exception as e:
            state.dbOk = False
            state.dbStatus = f"Load failed: {type(e).__name__}: {e}"

    ctrl.on_server_ready.add(ingest_campaign_every_time)

    return refresh_variable_list
