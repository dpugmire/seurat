"""Top-level Seurat UI composition."""

from trame.app import TrameComponent
from trame.ui.vuetify3 import SinglePageLayout
from trame.widgets import vuetify3 as vuetify

from seurat.widgets import InteractionRuntime, ResizeRuntime

from .context_menu import ContextMenu
from .dialogs import HelpDialog
from .grid import GridWorkspace
from .toolbar import QueryToolbar
from .variables import VariablePanel
from .workspace import WorkspaceMenu


class SeuratUI(TrameComponent):
    def __init__(self, server, campaign_name=""):
        super().__init__(server)
        self.query_toolbar = QueryToolbar(server)
        self.help_dialog = HelpDialog(server)
        self.workspace_menu = WorkspaceMenu(server)
        self.variable_panel = VariablePanel(server)
        self.grid_workspace = GridWorkspace(server)
        self.context_menu = ContextMenu(server)
        self.interaction_runtime = None
        self.resize_runtime = None
        self.layout = self.build(campaign_name)

    def build(self, campaign_name=""):
        with SinglePageLayout(self.server) as layout:
            layout.title.set_text(campaign_name or "Seurat")
            layout.icon.click = (
                "workspaceDrawerOpen = !workspaceDrawerOpen"
            )
            with vuetify.VNavigationDrawer(
                v_model=("workspaceDrawerOpen",),
                v_if=("workspaceDrawerOpen",),
                location="left",
                temporary=True,
                width=320,
            ) as drawer:
                self.workspace_menu.build()
            layout.drawer = drawer

            with layout.toolbar:
                self.query_toolbar.build()

            with layout.content:
                self.interaction_runtime = InteractionRuntime()
                self.resize_runtime = ResizeRuntime()
                self.help_dialog.build()
                with vuetify.VContainer(fluid=True, class_="pa-2"):
                    with vuetify.VRow(classes="seurat-main-row", no_gutters=True):
                        self.variable_panel.build()
                        self.grid_workspace.build()
                self.context_menu.build()

        return layout
