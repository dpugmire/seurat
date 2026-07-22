"""Top-level Seurat UI composition."""

from trame.app import TrameComponent
from trame.ui.vuetify3 import SinglePageLayout
from trame.widgets import html
from trame.widgets import vuetify3 as vuetify

from .context_menu import ContextMenu
from .dialogs import HelpDialog
from .grid import GridWorkspace
from .toolbar import QueryToolbar
from .variables import VariablePanel


class SeuratUI(TrameComponent):
    def __init__(self, server, campaign_name=""):
        super().__init__(server)
        self.query_toolbar = QueryToolbar(server)
        self.help_dialog = HelpDialog(server)
        self.variable_panel = VariablePanel(server)
        self.grid_workspace = GridWorkspace(server)
        self.context_menu = ContextMenu(server)
        self.layout = self.build(campaign_name)

    def build(self, campaign_name=""):
        with SinglePageLayout(self.server) as layout:
            layout.title.set_text(
                f"Campaign loaded: {campaign_name}"
                if campaign_name
                else "Campaign loaded"
            )

            with layout.toolbar:
                self.query_toolbar.build()

            with layout.content:
                self.help_dialog.build()
                with vuetify.VContainer(fluid=True, class_="pa-2"):
                    html.Div(
                        "",
                        id="seurat-reset-view-request",
                        style="display:none;",
                        raw_attrs=[
                            ':data-reset-view-request="JSON.stringify(resetViewRequest || {})"'
                        ],
                    )
                    with vuetify.VRow(classes="seurat-main-row", no_gutters=True):
                        self.variable_panel.build()
                        self.grid_workspace.build()
                self.context_menu.build()

        return layout
