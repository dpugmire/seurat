from typing import Dict

from config import CAMPAIGN_PATH, MAX_MOVIE_FRAMES, MOVIE_FPS
from query_parser import python_query_to_mongo
from state_init import clear_right_panes, fmt


def attach_controllers(server, db, collection, parse_campaign):
    state, ctrl = server.state, server.controller

    def refresh_variable_list():
        state.variableNames = db.distinct_variable_names(extra_filter=state.queryFilter or None)
        state.dbOk = db.ok
        state.dbStatus = "Connected" if db.ok else f"DB error: {db.last_error}"

    @ctrl.add("sort_sources")
    def sort_sources(field: str, **_):
        if not field:
            return

        if state.sourceSortField == field:
            state.sourceSortAsc = not bool(state.sourceSortAsc)
        else:
            state.sourceSortField = field
            state.sourceSortAsc = True

        asc = bool(state.sourceSortAsc)
        rows = list(state.sourceRows or [])

        def keyfn(row: Dict[str, str]):
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
            }
            for r in rows
        ]

        state.showSources = False
        if state.sourceSortField:
            sort_sources(state.sourceSortField)

        try:
            tiles = db.get_first_movie_tiles_for_variable(
                var_name,
                extra_filter=qf,
                limit=4,
                limit_frames=MAX_MOVIE_FRAMES,
                fps=MOVIE_FPS,
            )
            state.movieTiles = tiles
            state.movieDetailsOpen = {}
            state.movieStatus = ""
        except Exception as e:
            state.movieTiles = []
            state.movieDetailsOpen = {}
            state.movieStatus = f"Movie query/build failed: {type(e).__name__}: {e}"

    @ctrl.add("pick_var")
    def pick_var(var_name: str, **_):
        state.selectedVar = var_name

    @ctrl.add("toggle_sources")
    def toggle_sources(**_):
        state.showSources = not bool(state.showSources)

    @ctrl.add("toggle_movie_details")
    def toggle_movie_details(key: str, **_):
        k = str(key or "")
        current = bool((state.movieDetailsOpen or {}).get(k, False))
        state.movieDetailsOpen = {**(state.movieDetailsOpen or {}), k: (not current)}

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
            state.dbStatus = f"Loading {CAMPAIGN_PATH}..."

            collection.drop()
            parse_campaign(CAMPAIGN_PATH, collection)

            refresh_variable_list()
            state.dbStatus = f"Loaded {CAMPAIGN_PATH} • variables={len(state.variableNames)}"
        except Exception as e:
            state.dbOk = False
            state.dbStatus = f"Load failed: {type(e).__name__}: {e}"

    ctrl.on_server_ready.add(ingest_campaign_every_time)

    return refresh_variable_list
