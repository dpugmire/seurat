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
    state.variableGroups = []
    state.variableGroupCollapsed = {}
    state.selectedVar = ""

    state.queryText = ""
    state.queryStatus = ""
    state.queryError = ""
    state.queryFilter = {}
    state.queryViewLabel = "ALL"
    state.draggedVar = ""

    state.detailsSelectedVar = ""
    state.detailsNumSources = 0

    state.detailsGlobalMin = ""
    state.detailsGlobalMax = ""
    state.detailsMeanMin = ""
    state.detailsMeanMax = ""
    state.detailsMedianMin = ""
    state.detailsMedianMax = ""

    state.showSourcesModal = False
    state.sourceRows = []
    state.sourceSortField = SOURCE_FIELDS[0]
    state.sourceSortAsc = True
    state.selectedSourceKeys = []
    state.selectedSourceLabel = "All sources"

    state.movieTiles = []
    state.movieStatus = ""
    state.movieDetailsOpen = {}
    state.tileVisualizationBySource = {}

    state.gridCells = [
        {
            "variable_name": "",
            "visualization_name": "",
            "selected_visualization": "",
            "visualization_options": [],
            "producer": "",
            "casename": "",
            "file": "",
            "src": "",
            "media_type": "",
            "status": "empty",
            "note": "",
        }
        for _ in range(9)
    ]
    state.activeGridCell = -1
    state.contextMenuVisible = False
    state.contextMenuX = 0
    state.contextMenuY = 0
    state.contextMenuKind = ""
    state.contextMenuItem = ""
    state.contextMenuCellIndex = -1
    state.contextMenuCellVisualizationOptions = []
    state.contextMenuCellSelectedVisualization = ""


def clear_details(state) -> None:
    state.detailsSelectedVar = ""
    state.detailsNumSources = 0

    state.detailsGlobalMin = ""
    state.detailsGlobalMax = ""
    state.detailsMeanMin = ""
    state.detailsMeanMax = ""
    state.detailsMedianMin = ""
    state.detailsMedianMax = ""

    state.showSourcesModal = False
    state.sourceRows = []
    state.sourceSortField = SOURCE_FIELDS[0]
    state.sourceSortAsc = True
    state.selectedSourceKeys = []
    state.selectedSourceLabel = "All sources"


def clear_right_panes(state) -> None:
    clear_details(state)
    state.movieTiles = []
    state.movieStatus = ""
    state.movieDetailsOpen = {}
    state.tileVisualizationBySource = {}
    state.contextMenuVisible = False
    state.contextMenuCellVisualizationOptions = []
    state.contextMenuCellSelectedVisualization = ""
