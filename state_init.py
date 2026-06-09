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
    state.variableLabelsById = {}
    state.variableGroupCollapsed = {}
    state.showOnlyVisualizedVars = False
    state.selectedVar = ""

    state.queryText = ""
    state.queryStatus = ""
    state.queryError = ""
    state.queryFilter = {}
    state.queryViewLabel = "ALL"
    state.draggedVar = ""

    state.detailsSelectedVar = ""
    state.detailsSelectedVarId = ""
    state.detailsNumSources = 0

    state.detailsGlobalMin = ""
    state.detailsGlobalMax = ""
    state.detailsMeanMin = ""
    state.detailsMeanMax = ""
    state.detailsMedianMin = ""
    state.detailsMedianMax = ""

    state.showSourcesModal = False
    state.sourceDialogMode = "single"
    state.sourceDialogCellIndex = -1
    state.sourceRowsAll = []
    state.sourceRows = []
    state.sourceFilterDraftText = ""
    state.sourceFilterText = ""
    state.sourceFilterError = ""
    state.sourceSortField = SOURCE_FIELDS[0]
    state.sourceSortAsc = True
    state.selectedSourceKeys = []
    state.sourceDialogInitialSelectedSourceKeys = []
    state.selectedSourceLabel = "All sources"

    state.movieTiles = []
    state.movieStatus = ""
    state.movieDetailsOpen = {}
    state.tileVisualizationBySource = {}

    state.scalarPlotPolicy = "always"
    state.scalarPlotAlwaysForSession = False
    state.showScalarPlotDialog = False
    state.pendingScalarPlotVariableId = ""
    state.pendingScalarPlotCellIndex = -1
    state.pendingScalarPlotSourceFields = {}
    state.pendingScalarPlotSyncSelection = True
    state.scalarPlotDialogMessage = ""
    state.scalarPlotStatus = ""
    state.showPlotSettingsModal = False
    state.plotSettingsCellIndex = -1
    state.plotSettingsTitle = ""
    state.plotSettingsStatus = ""
    state.plotSettingsXAuto = True
    state.plotSettingsXMin = ""
    state.plotSettingsXMax = ""
    state.plotSettingsXScale = "linear"
    state.plotSettingsYAuto = True
    state.plotSettingsYMin = ""
    state.plotSettingsYMax = ""
    state.plotSettingsYScale = "linear"
    state.plotSettingsLineWidth = 2.5
    state.plotSettingsShowGrid = True
    state.plotSettingsShowCursor = True
    state.plotSettingsBackgroundColor = "#ffffff"
    state.plotSettingsGridColor = "#e8e8e8"
    state.plotSettingsCursorColor = "#111111"
    state.plotSettingsSeriesRows = []
    state.plotSettingsStandardColors = [
        "#c00000",
        "#ff0000",
        "#ffc000",
        "#ffff00",
        "#92d050",
        "#00b050",
        "#00b0f0",
        "#0070c0",
        "#002060",
        "#7030a0",
        "#000000",
    ]

    state.gridRows = 3
    state.gridCols = 3
    state.gridMinRows = 1
    state.gridMinCols = 1
    state.gridMaxRows = 8
    state.gridMaxCols = 8
    state.gridCellSize = 300
    state.gridMinCellSize = 160
    state.gridMaxCellSize = 520
    state.gridCells = [
        {
            "variable_name": "",
            "variable_id": "",
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
            "plot": {},
            "plot_settings": {},
            "status": "empty",
            "note": "",
        }
        for _ in range(state.gridRows * state.gridCols)
    ]
    state.activeGridCell = -1
    state.contextMenuVisible = False
    state.contextMenuX = 0
    state.contextMenuY = 0
    state.contextMenuKind = ""
    state.contextMenuItem = ""
    state.contextMenuItemLabel = ""
    state.contextMenuCellIndex = -1
    state.contextMenuCellHasVariable = False
    state.contextMenuCellCanAddSource = False
    state.contextMenuCellCanPlotSettings = False
    state.contextMenuCellVisualizationOptions = []
    state.contextMenuCellSelectedVisualization = ""


def clear_details(state) -> None:
    state.detailsSelectedVar = ""
    state.detailsSelectedVarId = ""
    state.detailsNumSources = 0

    state.detailsGlobalMin = ""
    state.detailsGlobalMax = ""
    state.detailsMeanMin = ""
    state.detailsMeanMax = ""
    state.detailsMedianMin = ""
    state.detailsMedianMax = ""

    state.showSourcesModal = False
    state.sourceDialogMode = "single"
    state.sourceDialogCellIndex = -1
    state.sourceRowsAll = []
    state.sourceRows = []
    state.sourceFilterDraftText = ""
    state.sourceFilterText = ""
    state.sourceFilterError = ""
    state.sourceSortField = SOURCE_FIELDS[0]
    state.sourceSortAsc = True
    state.selectedSourceKeys = []
    state.sourceDialogInitialSelectedSourceKeys = []
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
    state.contextMenuItemLabel = ""
    state.contextMenuCellHasVariable = False
    state.contextMenuCellCanAddSource = False
    state.showScalarPlotDialog = False
    state.pendingScalarPlotVariableId = ""
    state.pendingScalarPlotCellIndex = -1
    state.pendingScalarPlotSourceFields = {}
    state.scalarPlotDialogMessage = ""
    state.showPlotSettingsModal = False
    state.plotSettingsCellIndex = -1
    state.plotSettingsTitle = ""
    state.plotSettingsStatus = ""
    state.plotSettingsBackgroundColor = "#ffffff"
    state.plotSettingsGridColor = "#e8e8e8"
    state.plotSettingsCursorColor = "#111111"
    state.plotSettingsSeriesRows = []
