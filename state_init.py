from typing import Optional

from config import SOURCE_FIELDS


def fmt(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{value:.6g}"
    except Exception:
        return str(value)


def init_state(state, db) -> None:
    state.dbOk = db.ok
    state.dbStatus = "Connected" if db.ok else f"DB error: {db.last_error}"

    state.variableNames = []
    state.selectedVar = ""

    state.queryText = ""
    state.queryStatus = ""
    state.queryError = ""
    state.queryFilter = {}
    state.queryViewLabel = "ALL"

    state.detailsSelectedVar = ""
    state.detailsNumSources = 0

    state.detailsGlobalMin = ""
    state.detailsGlobalMax = ""
    state.detailsMeanMin = ""
    state.detailsMeanMax = ""
    state.detailsMedianMin = ""
    state.detailsMedianMax = ""

    state.showSources = False
    state.sourceRows = []
    state.sourceSortField = SOURCE_FIELDS[0]
    state.sourceSortAsc = True
    state.selectedSourceKey = ""
    state.selectedSourceFilter = {}

    state.movieTiles = []
    state.movieStatus = ""
    state.movieDetailsOpen = {}


def clear_details(state) -> None:
    state.detailsSelectedVar = ""
    state.detailsNumSources = 0

    state.detailsGlobalMin = ""
    state.detailsGlobalMax = ""
    state.detailsMeanMin = ""
    state.detailsMeanMax = ""
    state.detailsMedianMin = ""
    state.detailsMedianMax = ""

    state.showSources = False
    state.sourceRows = []
    state.sourceSortField = SOURCE_FIELDS[0]
    state.sourceSortAsc = True
    state.selectedSourceKey = ""
    state.selectedSourceFilter = {}


def clear_right_panes(state) -> None:
    clear_details(state)
    state.movieTiles = []
    state.movieStatus = ""
