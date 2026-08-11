"""Composition and Trame registration for Seurat's domain controllers."""

import inspect
from typing import Optional

from seurat.backends import LocalCampaignBackend, SeuratBackend

from .base import ControllerBase
from .catalog import CatalogControllerMixin
from .context import ControllerContext
from .context_menu import ContextMenuControllerMixin
from .grid import GridControllerMixin
from .lifecycle import LifecycleControllerMixin
from .query_assistant import QueryAssistantControllerMixin
from .sources import SourcesControllerMixin
from .visualization import VisualizationControllerMixin
from .workspace import WorkspaceControllerMixin


CONTROLLER_TYPES = (
    CatalogControllerMixin,
    QueryAssistantControllerMixin,
    SourcesControllerMixin,
    GridControllerMixin,
    VisualizationControllerMixin,
    ContextMenuControllerMixin,
    WorkspaceControllerMixin,
    LifecycleControllerMixin,
)


class SeuratController(
    CatalogControllerMixin,
    QueryAssistantControllerMixin,
    SourcesControllerMixin,
    GridControllerMixin,
    VisualizationControllerMixin,
    ContextMenuControllerMixin,
    WorkspaceControllerMixin,
    LifecycleControllerMixin,
    ControllerBase,
):
    def register(self):
        for controller_type in CONTROLLER_TYPES:
            for action_name, method_name in controller_type.ACTION_BINDINGS:
                method = getattr(self, method_name)
                if inspect.iscoroutinefunction(method):
                    self.ctrl.set(action_name, clear=True)(method)
                else:
                    self.ctrl.add(action_name)(method)
            for trigger_name, method_name in controller_type.TRIGGER_BINDINGS:
                self.ctrl.trigger(trigger_name)(getattr(self, method_name))
            for state_names, method_name in controller_type.STATE_CHANGE_BINDINGS:
                self.state.change(*state_names)(getattr(self, method_name))
        self.ctrl.on_server_ready.add(self.ingest_campaign_every_time)
        return self


def attach_controllers(
    server,
    db,
    collection,
    parse_campaign,
    campaign_path: str,
    image_association_schema_path: str = "",
    campaign_schema_path: str = "",
    backend: Optional[SeuratBackend] = None,
    query_translator=None,
):
    catalog_backend = backend if backend is not None else LocalCampaignBackend(db)
    context = ControllerContext(
        server=server,
        backend=catalog_backend,
        db=db,
        collection=collection,
        parse_campaign=parse_campaign,
        campaign_path=campaign_path,
        image_association_schema_path=image_association_schema_path,
        campaign_schema_path=campaign_schema_path,
        query_translator=query_translator,
    )
    controller = SeuratController(context).register()
    return controller.refresh_variable_list
