"""Base state and dependencies for domain controller mixins."""

from application import SeuratApplication
from seurat.models import grid_layout

from .context import ControllerContext


class ControllerBase:
    GRID_MIN_ROWS = grid_layout.GRID_MIN_ROWS
    GRID_MIN_COLS = grid_layout.GRID_MIN_COLS
    GRID_MAX_ROWS = grid_layout.GRID_MAX_ROWS
    GRID_MAX_COLS = grid_layout.GRID_MAX_COLS
    GRID_HEADER_HEIGHT = grid_layout.GRID_HEADER_HEIGHT
    GRID_MIN_TRACK_WEIGHT = grid_layout.GRID_MIN_TRACK_WEIGHT
    GRID_MAX_TRACK_WEIGHT = grid_layout.GRID_MAX_TRACK_WEIGHT

    def __init__(self, context: ControllerContext):
        self.context = context
        self.server = context.server
        self.state = context.server.state
        self.ctrl = context.server.controller
        self.backend = context.backend
        self.db = context.db
        self.collection = context.collection
        self.parse_campaign = context.parse_campaign
        self.campaign_path = context.campaign_path
        self.image_association_schema_path = context.image_association_schema_path
        self.campaign_schema_path = context.campaign_schema_path
        self.application = SeuratApplication(backend=context.backend)
        self.plugin_source_variables_cache = {}
