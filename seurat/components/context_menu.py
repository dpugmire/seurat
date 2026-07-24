"""Grid and variable context-menu component."""

from trame.app import TrameComponent
from trame.widgets import html
from trame.widgets import vuetify3 as vuetify


def _menu_item(label, icon, click, classes="menu-item"):
    with html.Div(classes=classes, click=click):
        vuetify.VIcon(icon, size=18, classes="menu-item-icon")
        html.Span(label)


class ContextMenu(TrameComponent):
    def build(self):
        ctrl = self.ctrl
        with html.Div(
            id="seurat-context-menu",
            v_show=("contextMenuVisible",),
            raw_attrs=[
                ':style="{ position: \'fixed\', zIndex: 9999, left: (contextMenuX || 0) + \'px\', top: (contextMenuY || 0) + \'px\' }"'
            ],
        ):
            html.Div("{{ contextMenuItemLabel || contextMenuItem || 'Menu' }}", classes="menu-label")

            with html.Div(v_if="contextMenuKind === 'item'"):
                _menu_item(
                    "Add to workspace",
                    "mdi-view-grid-plus-outline",
                    ctrl.context_menu_item_add,
                )
                _menu_item(
                    "Select variable",
                    "mdi-cursor-default-click-outline",
                    ctrl.context_menu_item_select,
                )

            with html.Div(v_if="contextMenuKind === 'cell'"):
                with vuetify.Template(v_if="!contextMenuCellHasVariable"):
                    _menu_item(
                        "Select panel",
                        "mdi-cursor-default-click-outline",
                        ctrl.context_menu_cell_select,
                    )
                with vuetify.Template(v_if="contextMenuCellCanResetView"):
                    _menu_item(
                        "Reset view",
                        "mdi-restore",
                        ctrl.context_menu_cell_reset_view,
                    )
                with vuetify.Template(v_if="contextMenuCellHasVariable && !contextMenuCellCanPlotSettings"):
                    _menu_item(
                        "Sources…",
                        "mdi-database-outline",
                        ctrl.context_menu_cell_sources,
                    )
                with vuetify.Template(v_if="contextMenuCellCanAddSource"):
                    _menu_item(
                        "Add source",
                        "mdi-database-plus-outline",
                        ctrl.context_menu_cell_add_source,
                    )
                with vuetify.Template(v_if="contextMenuCellCanPlotSettings"):
                    _menu_item(
                        "Plot settings…",
                        "mdi-tune-vertical",
                        ctrl.context_menu_cell_plot_settings,
                    )
                with vuetify.Template(v_if="contextMenuCellCanScalarFieldSettings"):
                    _menu_item(
                        "Plot options…",
                        "mdi-palette-outline",
                        ctrl.context_menu_cell_scalar_field_settings,
                    )
                with vuetify.Template(v_if="gridLayoutMode === 'spanning'"):
                    with html.Div(classes="menu-submenu"):
                        with html.Div(classes="menu-item menu-submenu-trigger"):
                            vuetify.VIcon(
                                "mdi-arrow-expand",
                                size=18,
                                classes="menu-item-icon",
                            )
                            html.Span("Span")
                            html.Span("›", classes="menu-submenu-arrow")
                        with html.Div(classes="menu-submenu-panel"):
                            _menu_item(
                                "Span right",
                                "mdi-arrow-expand-right",
                                ctrl.context_menu_cell_span_right,
                            )
                            _menu_item(
                                "Span down",
                                "mdi-arrow-expand-down",
                                ctrl.context_menu_cell_span_down,
                            )
                            _menu_item(
                                "Shrink width",
                                "mdi-arrow-collapse-horizontal",
                                ctrl.context_menu_cell_shrink_width,
                            )
                            _menu_item(
                                "Shrink height",
                                "mdi-arrow-collapse-vertical",
                                ctrl.context_menu_cell_shrink_height,
                            )
                            _menu_item(
                                "Reset span",
                                "mdi-restore",
                                ctrl.context_menu_cell_reset_span,
                            )
                with vuetify.Template(v_if="(contextMenuCellSourcePlugins || []).length"):
                    html.Div("Run plugin", classes="menu-section")
                    with vuetify.Template(v_for="plugin in contextMenuCellSourcePlugins", key="plugin.plugin_id"):
                        with html.Div(
                            classes="menu-item",
                            click=(ctrl.context_menu_cell_run_source_plugin, "[plugin.plugin_id]"),
                        ):
                            vuetify.VIcon(
                                "mdi-puzzle-outline",
                                size=18,
                                classes="menu-item-icon",
                            )
                            html.Span("{{ plugin.label }}")
                with vuetify.Template(v_if="(contextMenuCellVisualizationOptions || []).length"):
                    html.Div("Visualization type", classes="menu-section")
                    with vuetify.Template(v_for="vis in contextMenuCellVisualizationOptions", key="vis"):
                        with html.Div(
                            classes="menu-item",
                            click=(ctrl.context_menu_cell_pick_visualization, "[vis]"),
                        ):
                            vuetify.VIcon(
                                ("vis === contextMenuCellSelectedVisualization ? 'mdi-check' : 'mdi-chart-box-outline'",),
                                size=18,
                                classes="menu-item-icon",
                            )
                            html.Span("{{ vis }}")
                with vuetify.Template(v_if="contextMenuCellHasVariable"):
                    html.Div(classes="menu-danger-divider")
                    _menu_item(
                        "Clear panel",
                        "mdi-delete-outline",
                        ctrl.context_menu_cell_clear,
                        classes="menu-item danger",
                    )
