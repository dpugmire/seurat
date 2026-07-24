"""Visualization grid and layout controls."""

from trame.app import TrameComponent
from trame.widgets import html
from trame.widgets import vuetify3 as vuetify

from seurat.widgets import GridRuntime

from .dialogs import (
    PlotSettingsPanel,
    PluginOptionsPanel,
    ScalarFieldSettingsPanel,
    ScalarPlotDialog,
    SourceDialog,
)


def _build_grid_size_picker(ctrl):
    with html.Div(classes="seurat-toolbar-menu", style="margin-top:10px; width:100%;"):
        with html.Button(
            classes="seurat-grid-size-trigger",
            raw_attrs=['type="button"'],
            title="Grid size",
        ):
            html.Span("Grid size", classes="seurat-grid-size-trigger-label")
            html.Span("{{ gridRows + ' x ' + gridCols + ' ▾' }}", classes="seurat-grid-size-trigger-value")
        with vuetify.VMenu(
            activator="parent",
            location="bottom start",
            close_on_content_click=False,
        ):
            with vuetify.VCard(classes="seurat-grid-size-popover", elevation=4):
                with vuetify.VCardText(class_="pa-2"):
                    html.Div("Grid size", classes="seurat-toolbar-popover-title")
                    with html.Div(classes="seurat-grid-picker"):
                        for picker_row in range(1, 9):
                            for picker_col in range(1, 9):
                                html.Button(
                                    "",
                                    classes="seurat-grid-picker-cell",
                                    click=(ctrl.set_grid_layout_size, f"[{picker_row}, {picker_col}]"),
                                    raw_attrs=[
                                        'type="button"',
                                        f'title="{picker_row} x {picker_col}"',
                                        f':class="{{ selected: gridRows >= {picker_row} && gridCols >= {picker_col}, current: gridRows === {picker_row} && gridCols === {picker_col} }}"',
                                    ],
                                )
                    html.Div(
                        "{{ gridRows + ' x ' + gridCols }}",
                        class_="text-caption seurat-grid-picker-label",
                    )
                    with html.Div(classes="seurat-grid-layout-stepper"):
                        html.Span("Rows", class_="text-caption seurat-grid-layout-stepper-label")
                        html.Button(
                            "-",
                            classes="seurat-grid-layout-btn",
                            click=ctrl.delete_grid_row,
                            raw_attrs=['type="button"', ':disabled="gridRows <= gridMinRows"'],
                            title="Delete active row or last row",
                        )
                        html.Span("{{ gridRows }}", class_="text-caption text-center")
                        html.Button(
                            "+",
                            classes="seurat-grid-layout-btn",
                            click=ctrl.add_grid_row,
                            raw_attrs=['type="button"', ':disabled="gridRows >= gridMaxRows"'],
                            title="Add row",
                        )
                    with html.Div(classes="seurat-grid-layout-stepper"):
                        html.Span("Cols", class_="text-caption seurat-grid-layout-stepper-label")
                        html.Button(
                            "-",
                            classes="seurat-grid-layout-btn",
                            click=ctrl.delete_grid_column,
                            raw_attrs=['type="button"', ':disabled="gridCols <= gridMinCols"'],
                            title="Delete active column or last column",
                        )
                        html.Span("{{ gridCols }}", class_="text-caption text-center")
                        html.Button(
                            "+",
                            classes="seurat-grid-layout-btn",
                            click=ctrl.add_grid_column,
                            raw_attrs=['type="button"', ':disabled="gridCols >= gridMaxCols"'],
                            title="Add column",
                        )


def _build_grid_settings_popover(ctrl):
    html.Div("Settings", classes="seurat-toolbar-popover-title")
    with html.Div(classes="seurat-settings-section"):
        html.Div("Layout", classes="seurat-settings-section-title")
        html.Div("Cell layout", classes="seurat-grid-sizing-section-label")
        with html.Div(classes="seurat-grid-sizing-mode"):
            html.Button(
                "Uniform",
                classes="seurat-grid-sizing-mode-btn",
                click=(ctrl.set_grid_layout_mode, "['uniform']"),
                raw_attrs=[
                    'type="button"',
                    ':class="{ active: gridLayoutMode !== \'spanning\' }"',
                ],
                title="Use one cell per grid slot",
            )
            html.Button(
                "Spanning",
                classes="seurat-grid-sizing-mode-btn",
                click=(ctrl.set_grid_layout_mode, "['spanning']"),
                raw_attrs=[
                    'type="button"',
                    ':class="{ active: gridLayoutMode === \'spanning\' }"',
                ],
                title="Allow cells to span multiple rows or columns",
            )
        html.Div("Size mode", classes="seurat-grid-sizing-section-label")
        with html.Div(classes="seurat-grid-sizing-mode"):
            html.Button(
                "Static",
                classes="seurat-grid-sizing-mode-btn",
                click=(ctrl.set_grid_sizing_mode, "['static']"),
                raw_attrs=[
                    'type="button"',
                    ':class="{ active: gridSizingMode !== \'fit\' }"',
                ],
                title="Use fixed-size cells",
            )
            html.Button(
                "Fit window",
                classes="seurat-grid-sizing-mode-btn",
                click=(ctrl.set_grid_sizing_mode, "['fit']"),
                raw_attrs=[
                    'type="button"',
                    ':class="{ active: gridSizingMode === \'fit\' }"',
                ],
                title="Resize cells to fill the grid viewport",
            )
        with vuetify.Template(v_if="gridSizingMode !== 'fit'"):
            html.Div("Cell size", classes="seurat-grid-sizing-section-label")
            with html.Div(classes="seurat-size-stepper"):
                html.Button(
                    "-",
                    classes="seurat-grid-layout-btn",
                    click=(ctrl.set_grid_cell_size, "[Number(gridCellSize || 300) - 10]"),
                    raw_attrs=['type="button"'],
                    title="Decrease cell size",
                )
                html.Input(
                    v_model=("gridCellSize",),
                    classes="seurat-size-stepper-input",
                    change=(ctrl.set_grid_cell_size, "[$event.target.value]"),
                    raw_attrs=[
                        'type="number"',
                        ':min="gridMinCellSize"',
                        ':max="gridMaxCellSize"',
                        'step="10"',
                        'aria-label="Cell size"',
                    ],
                )
                html.Button(
                    "+",
                    classes="seurat-grid-layout-btn",
                    click=(ctrl.set_grid_cell_size, "[Number(gridCellSize || 300) + 10]"),
                    raw_attrs=['type="button"'],
                    title="Increase cell size",
                )
                html.Span("px", classes="seurat-size-stepper-unit")
            html.Button(
                "Reset track sizes",
                classes="seurat-grid-reset-tracks-btn",
                click=ctrl.reset_grid_track_sizes,
                raw_attrs=['type="button"'],
                title="Reset all rows and columns to the current cell size",
            )
        with vuetify.Template(v_if="gridSizingMode === 'fit'"):
            html.Div("Minimum cell size", classes="seurat-grid-sizing-section-label")
            with html.Div(classes="seurat-size-stepper"):
                html.Button(
                    "-",
                    classes="seurat-grid-layout-btn",
                    click=(ctrl.set_grid_fit_min_cell_size, "[Number(gridFitMinCellSize || 180) - 10]"),
                    raw_attrs=['type="button"'],
                    title="Decrease minimum cell size",
                )
                html.Input(
                    v_model=("gridFitMinCellSize",),
                    classes="seurat-size-stepper-input",
                    change=(ctrl.set_grid_fit_min_cell_size, "[$event.target.value]"),
                    raw_attrs=[
                        'type="number"',
                        ':min="gridMinCellSize"',
                        ':max="gridMaxFitMinCellSize"',
                        'step="10"',
                        'aria-label="Minimum cell size"',
                    ],
                )
                html.Button(
                    "+",
                    classes="seurat-grid-layout-btn",
                    click=(ctrl.set_grid_fit_min_cell_size, "[Number(gridFitMinCellSize || 180) + 10]"),
                    raw_attrs=['type="button"'],
                    title="Increase minimum cell size",
                )
                html.Span("px", classes="seurat-size-stepper-unit")
        _build_grid_size_picker(ctrl)
    with html.Div(classes="seurat-settings-section"):
        html.Div("Scalar plots", classes="seurat-settings-section-title")
        with html.Div(classes="seurat-settings-row"):
            html.Span("Create curves", class_="text-caption")
            with html.Select(
                v_model=("scalarPlotPolicy",),
                classes="seurat-scalar-plot-policy",
                title="Generated scalar plot behavior",
            ):
                html.Option("Ask", value="ask")
                html.Option("Generate", value="always")
                html.Option("Never", value="never")


def _build_grid_layout_controls(ctrl):
    with html.Div(classes="seurat-grid-layout-controls"):
        with html.Div(classes="seurat-toolbar-menu"):
            with html.Button(
                classes="seurat-toolbar-menu-btn seurat-toolbar-icon-btn",
                raw_attrs=[
                    'type="button"',
                    'aria-label="Settings"',
                ],
                title="Settings",
            ):
                vuetify.VIcon("mdi-cog-outline", size=18)
            with vuetify.VMenu(
                activator="parent",
                location="bottom end",
                close_on_content_click=False,
            ):
                with vuetify.VCard(classes="seurat-settings-popover", elevation=4):
                    with vuetify.VCardText(class_="pa-2"):
                        _build_grid_settings_popover(ctrl)


class GridWorkspace(TrameComponent):
    def __init__(self, server):
        super().__init__(server)
        self.runtime = None
        self.source_dialog = SourceDialog(server)
        self.scalar_plot_dialog = ScalarPlotDialog(server)
        self.plot_settings_panel = PlotSettingsPanel(server)
        self.plugin_options_panel = PluginOptionsPanel(server)
        self.scalar_field_settings_panel = ScalarFieldSettingsPanel(server)

    def build(self):
        ctrl = self.ctrl
        with vuetify.VCol(
            classes="seurat-content-column",
            style="display:flex; flex-direction:column;",
        ):
            with vuetify.VCard(
                variant="flat",
                classes="seurat-workspace-card",
            ):
                with vuetify.VCardText(
                    classes="seurat-workspace-card-content",
                ):
                    self.runtime = GridRuntime()
                    html.Div(
                        "",
                        id="seurat-reset-view-request",
                        style="display:none;",
                        raw_attrs=[
                            ':data-reset-view-request="JSON.stringify(resetViewRequest || {})"'
                        ],
                    )
                    with html.Div(classes="seurat-vcr-bar seurat-grid-controls-header"):
                        with html.Div(classes="seurat-workspace-meta"):
                            html.Div("Workspace", classes="seurat-workspace-name")
                            html.Div(
                                "{{ gridRows + ' × ' + gridCols }}",
                                classes="seurat-workspace-dimensions",
                            )
                        with html.Div(classes="seurat-vcr-controls"):
                            with html.Button(
                                classes="seurat-vcr-btn",
                                raw_attrs=[
                                    'type="button"',
                                    'data-vcr-action="start"',
                                ],
                                title="Jump to start",
                            ):
                                vuetify.VIcon("mdi-skip-previous", size=17)
                            with html.Button(
                                classes="seurat-vcr-btn",
                                raw_attrs=[
                                    'type="button"',
                                    'data-vcr-action="back"',
                                ],
                                title="Back step",
                            ):
                                vuetify.VIcon("mdi-step-backward", size=17)
                            with html.Button(
                                classes="seurat-vcr-btn",
                                raw_attrs=[
                                    'type="button"',
                                    'data-vcr-action="play"',
                                ],
                                title="Play all",
                            ):
                                vuetify.VIcon("mdi-play", size=17)
                            with html.Button(
                                classes="seurat-vcr-btn",
                                raw_attrs=[
                                    'type="button"',
                                    'data-vcr-action="pause"',
                                ],
                                title="Pause all",
                            ):
                                vuetify.VIcon("mdi-pause", size=17)
                            with html.Button(
                                classes="seurat-vcr-btn",
                                raw_attrs=[
                                    'type="button"',
                                    'data-vcr-action="forward"',
                                ],
                                title="Forward step",
                            ):
                                vuetify.VIcon("mdi-step-forward", size=17)
                            with html.Button(
                                classes="seurat-vcr-btn",
                                raw_attrs=[
                                    'type="button"',
                                    'data-vcr-action="end"',
                                ],
                                title="Jump to end",
                            ):
                                vuetify.VIcon("mdi-skip-next", size=17)
                        html.Span(
                            "Step = 0",
                            id="seurat-vcr-time-value",
                            class_="text-caption seurat-vcr-time",
                        )
                        html.Input(
                            type="range",
                            id="seurat-vcr-step-slider",
                            classes="seurat-vcr-slider",
                            raw_attrs=[
                                'min="0"',
                                'max="20"',
                                'step="1"',
                                'value="0"',
                                'aria-label="Timestep"',
                                'title="Timestep (frame index)"',
                            ],
                        )
                        _build_grid_layout_controls(ctrl)
                    with vuetify.Template(v_if="scalarPlotStatus"):
                        html.Div("{{ scalarPlotStatus }}", class_="text-caption mb-2", style="color:#8a4b00;")
                    with html.Div(
                        classes="seurat-main-grid",
                        raw_attrs=[
                            ':data-grid-sizing-mode="gridSizingMode"',
                            ':data-grid-cols="gridCols"',
                            ':data-grid-rows="gridRows"',
                            ':data-grid-column-sizes="(gridColumnSizes || []).join(\',\')"',
                            ':data-grid-row-sizes="(gridRowSizes || []).join(\',\')"',
                            ':data-grid-column-weights="(gridColumnWeights || []).join(\',\')"',
                            ':data-grid-row-weights="(gridRowWeights || []).join(\',\')"',
                            ':data-grid-min-column-size="gridMinCellSize"',
                            ':data-grid-max-column-size="gridMaxCellSize"',
                            ':data-grid-min-row-size="Number(gridMinCellSize || 80) + 32"',
                            ':data-grid-max-row-size="Number(gridMaxCellSize || 5000) + 32"',
                            ':data-grid-fit-min-column-size="gridFitMinCellSize"',
                            ':data-grid-fit-min-row-size="Number(gridFitMinCellSize || 180) + 32"',
                            ':data-grid-column-fallback="gridCellSize"',
                            ':data-grid-row-fallback="Number(gridCellSize || 300) + 32"',
                        ],
                        style=(
                            "('display:grid;'"
                            " + ((gridSizingMode === 'fit')"
                            " ? ('grid-template-columns:' + String(gridFitColumnTemplate || ('repeat(' + gridCols + ', minmax(' + Number(gridFitMinCellSize || 180) + 'px, 1fr))')) + ';'"
                            " + 'grid-template-rows:' + String(gridFitRowTemplate || ('repeat(' + gridRows + ', minmax(' + (Number(gridFitMinCellSize || 180) + 32) + 'px, 1fr))')) + ';'"
                            " + 'justify-content:stretch;'"
                            " + 'align-content:stretch;')"
                            " : ('grid-template-columns:' + String(gridColumnTemplate || ('repeat(' + gridCols + ', ' + Number(gridCellSize || 300) + 'px)')) + ';'"
                            " + 'grid-template-rows:' + String(gridRowTemplate || ('repeat(' + gridRows + ', ' + (Number(gridCellSize || 300) + 32) + 'px)')) + ';'"
                            " + 'justify-content:center;'"
                            " + 'align-content:start;'))"
                            " + 'flex:1 1 auto;'"
                            " + 'min-height:0;'"
                            " + 'overflow:auto;'"
                            " + 'width:100%;'"
                            " + 'box-sizing:border-box;'"
                            " + 'gap:var(--seurat-space-3);'"
                            " + 'padding:var(--seurat-space-3);'"
                            " + 'background:var(--seurat-workspace-bg);'"
                            " + 'border:1px solid var(--seurat-border);'"
                            " + 'border-radius:var(--seurat-radius-lg);')",
                        ),
                    ):
                        with vuetify.Template(v_for="(tile, i) in gridCells", key="i"):
                            with html.Div(
                                click=(
                                    ctrl.set_active_grid_cell,
                                    "[i, (($event && $event.target && $event.target.closest && $event.target.closest('.seurat-cell-menu, .seurat-timeline-driver-btn, .seurat-grid-track-resize-handle')) ? 1 : 0), (($event && $event.shiftKey) ? 1 : 0)]",
                                ),
                                classes="seurat-dropcell",
                                raw_attrs=[
                                    ':data-cell-index="i"',
                                    ':data-cell-filled="((tile && tile.variable_name) ? 1 : 0)"',
                                    ':data-cell-active="(activeGridCell === i ? 1 : 0)"',
                                    ':data-timeline-driver="(timelineDriverCell === i ? 1 : 0)"',
                                    ':aria-selected="activeGridCell === i ? \'true\' : \'false\'"',
                                    ':draggable="!!(tile && tile.variable_name)"',
                                ],
                                style=(
                                    "((gridLayoutMode === 'spanning')"
                                    " ? ('grid-row:' + Number((tile && tile.grid_row) || (Math.floor(i / gridCols) + 1)) + ' / span ' + Number((tile && tile.row_span) || 1) + ';grid-column:' + Number((tile && tile.grid_col) || ((i % gridCols) + 1)) + ' / span ' + Number((tile && tile.col_span) || 1) + ';')"
                                    " : '')"
                                    " + ((gridLayoutMode === 'spanning')"
                                    " ? 'width:100%; height:100%; min-width:0; min-height:0;'"
                                    " : ((gridSizingMode === 'fit')"
                                    " ? ('width:100%; height:100%; min-width:' + Number(gridFitMinCellSize || 180) + 'px; min-height:' + (Number(gridFitMinCellSize || 180) + 32) + 'px;')"
                                    " : 'width:100%; height:100%; min-width:0; min-height:0;'))"
                                    " + 'overflow:hidden; cursor:pointer; display:flex; flex-direction:column; position:relative; box-sizing:border-box;'"
                                    " + 'border:1px solid var(--seurat-border); border-radius:var(--seurat-radius-lg); background:var(--seurat-surface);'"
                                    " + ((activeGridCell === i) ? 'outline:2px solid var(--seurat-accent); outline-offset:1px; z-index:2;' : '')"
                                    " + ((gridLayoutMode === 'spanning' && tile && tile.grid_hidden) ? 'display:none;' : '')",
                                ),
                            ):
                                html.Div(
                                    classes="seurat-grid-track-resize-handle seurat-grid-col-resize-handle seurat-grid-left-resize-handle",
                                    v_if=(
                                        "gridSizingMode !== 'fit'"
                                        " && !(gridLayoutMode === 'spanning' && tile && tile.grid_hidden)"
                                        " && ((gridLayoutMode === 'spanning'"
                                        " ? Number((tile && tile.grid_col) || ((i % gridCols) + 1))"
                                        " : ((i % gridCols) + 1)) === 1)"
                                    ),
                                    raw_attrs=[
                                        'role="separator"',
                                        'aria-orientation="vertical"',
                                        'title="Drag to resize column"',
                                        'data-resize-edge="left"',
                                        'data-col-index="0"',
                                    ],
                                )
                                html.Div(
                                    classes="seurat-grid-track-resize-handle seurat-grid-col-resize-handle",
                                    v_if=(
                                        "!(gridLayoutMode === 'spanning' && tile && tile.grid_hidden)"
                                        " && (gridSizingMode !== 'fit' || ((gridLayoutMode === 'spanning'"
                                        " ? (Number((tile && tile.grid_col) || ((i % gridCols) + 1)) + Number((tile && tile.col_span) || 1) - 1)"
                                        " : ((i % gridCols) + 1)) < Number(gridCols || 0)))"
                                    ),
                                    raw_attrs=[
                                        'role="separator"',
                                        'aria-orientation="vertical"',
                                        'title="Drag to resize column"',
                                        'data-resize-edge="right"',
                                        ':data-col-index="gridLayoutMode === \'spanning\' ? (Number((tile && tile.grid_col) || ((i % gridCols) + 1)) + Number((tile && tile.col_span) || 1) - 2) : (i % gridCols)"',
                                    ],
                                )
                                html.Div(
                                    classes="seurat-grid-track-resize-handle seurat-grid-row-resize-handle seurat-grid-top-resize-handle",
                                    v_if=(
                                        "gridSizingMode !== 'fit'"
                                        " && !(gridLayoutMode === 'spanning' && tile && tile.grid_hidden)"
                                        " && ((gridLayoutMode === 'spanning'"
                                        " ? Number((tile && tile.grid_row) || (Math.floor(i / gridCols) + 1))"
                                        " : (Math.floor(i / gridCols) + 1)) === 1)"
                                    ),
                                    raw_attrs=[
                                        'role="separator"',
                                        'aria-orientation="horizontal"',
                                        'title="Drag to resize row"',
                                        'data-resize-edge="top"',
                                        'data-row-index="0"',
                                    ],
                                )
                                html.Div(
                                    classes="seurat-grid-track-resize-handle seurat-grid-row-resize-handle",
                                    v_if=(
                                        "!(gridLayoutMode === 'spanning' && tile && tile.grid_hidden)"
                                        " && (gridSizingMode !== 'fit' || ((gridLayoutMode === 'spanning'"
                                        " ? (Number((tile && tile.grid_row) || (Math.floor(i / gridCols) + 1)) + Number((tile && tile.row_span) || 1) - 1)"
                                        " : (Math.floor(i / gridCols) + 1)) < Number(gridRows || 0)))"
                                    ),
                                    raw_attrs=[
                                        'role="separator"',
                                        'aria-orientation="horizontal"',
                                        'title="Drag to resize row"',
                                        'data-resize-edge="bottom"',
                                        ':data-row-index="gridLayoutMode === \'spanning\' ? (Number((tile && tile.grid_row) || (Math.floor(i / gridCols) + 1)) + Number((tile && tile.row_span) || 1) - 2) : Math.floor(i / gridCols)"',
                                    ],
                                )
                                html.Div(
                                    classes="seurat-grid-track-resize-handle seurat-grid-corner-resize-handle seurat-grid-corner-bottom-left",
                                    v_if=(
                                        "!(gridLayoutMode === 'spanning' && tile && tile.grid_hidden)"
                                        " && (gridSizingMode !== 'fit' || ("
                                        "((gridLayoutMode === 'spanning' ? Number((tile && tile.grid_col) || ((i % gridCols) + 1)) : ((i % gridCols) + 1)) > 1)"
                                        " && ((gridLayoutMode === 'spanning' ? (Number((tile && tile.grid_row) || (Math.floor(i / gridCols) + 1)) + Number((tile && tile.row_span) || 1) - 1) : (Math.floor(i / gridCols) + 1)) < Number(gridRows || 0))"
                                        "))"
                                    ),
                                    raw_attrs=[
                                        'role="separator"',
                                        'aria-orientation="vertical"',
                                        'title="Drag to resize row and column"',
                                        'data-col-edge="left"',
                                        'data-row-edge="bottom"',
                                        ':data-col-index="gridLayoutMode === \'spanning\' ? (Number((tile && tile.grid_col) || ((i % gridCols) + 1)) - 1) : (i % gridCols)"',
                                        ':data-row-index="gridLayoutMode === \'spanning\' ? (Number((tile && tile.grid_row) || (Math.floor(i / gridCols) + 1)) + Number((tile && tile.row_span) || 1) - 2) : Math.floor(i / gridCols)"',
                                    ],
                                )
                                html.Div(
                                    classes="seurat-grid-track-resize-handle seurat-grid-corner-resize-handle seurat-grid-corner-bottom-right",
                                    v_if=(
                                        "!(gridLayoutMode === 'spanning' && tile && tile.grid_hidden)"
                                        " && (gridSizingMode !== 'fit' || ("
                                        "((gridLayoutMode === 'spanning' ? (Number((tile && tile.grid_col) || ((i % gridCols) + 1)) + Number((tile && tile.col_span) || 1) - 1) : ((i % gridCols) + 1)) < Number(gridCols || 0))"
                                        " && ((gridLayoutMode === 'spanning' ? (Number((tile && tile.grid_row) || (Math.floor(i / gridCols) + 1)) + Number((tile && tile.row_span) || 1) - 1) : (Math.floor(i / gridCols) + 1)) < Number(gridRows || 0))"
                                        "))"
                                    ),
                                    raw_attrs=[
                                        'role="separator"',
                                        'aria-orientation="vertical"',
                                        'title="Drag to resize row and column"',
                                        'data-col-edge="right"',
                                        'data-row-edge="bottom"',
                                        ':data-col-index="gridLayoutMode === \'spanning\' ? (Number((tile && tile.grid_col) || ((i % gridCols) + 1)) + Number((tile && tile.col_span) || 1) - 2) : (i % gridCols)"',
                                        ':data-row-index="gridLayoutMode === \'spanning\' ? (Number((tile && tile.grid_row) || (Math.floor(i / gridCols) + 1)) + Number((tile && tile.row_span) || 1) - 2) : Math.floor(i / gridCols)"',
                                    ],
                                )
                                with vuetify.Template(v_if="tile && tile.variable_name"):
                                    with html.Div(
                                        classes="seurat-panel-header",
                                        raw_attrs=[
                                            ":class=\"{ 'is-active': activeGridCell === i, 'is-selected': (selectedGridCellMap || {})[String(i)] }\"",
                                        ],
                                    ):
                                        html.Div(
                                            "{{ tile.display_title || tile.variable_name || 'variable' }}",
                                            classes="seurat-panel-title",
                                            raw_attrs=[
                                                ':title="tile.display_title || tile.variable_name || \'variable\'"',
                                            ],
                                        )
                                        with html.Button(
                                            v_if=(
                                                "(tile.time_values && tile.time_values.length)"
                                                " || (tile.plot && tile.plot.series && tile.plot.series.length"
                                                " && (String(tile.plot.x_label || '').toLowerCase() === 'time'"
                                                " || String(tile.plot.x_label || '').toLowerCase() === 'physical time'))"
                                            ),
                                            classes="seurat-timeline-driver-btn",
                                            click=(ctrl.toggle_timeline_driver_cell, "[i]"),
                                            raw_attrs=[
                                                'type="button"',
                                                ':aria-pressed="timelineDriverCell === i ? \'true\' : \'false\'"',
                                                'aria-label="Use as timeline driver"',
                                            ],
                                            title="Use as timeline driver",
                                        ):
                                            html.Span(
                                                classes="seurat-timeline-clock-icon",
                                                raw_attrs=['aria-hidden="true"'],
                                            )
                                        with html.Button(
                                            classes="seurat-cell-menu",
                                            click=(
                                                ctrl.open_cell_context_menu,
                                                "[i, $event.clientX, $event.clientY]",
                                            ),
                                            raw_attrs=[
                                                'type="button"',
                                                'aria-label="Panel menu"',
                                            ],
                                            title="Panel menu",
                                    ):
                                            vuetify.VIcon("mdi-dots-vertical", size=19)
                                        html.Span(
                                            "{{ tile.media_type === 'plot1d' ? 'Trace' : (String(tile.media_type || '').includes('image') ? 'Image' : ((String(tile.media_type || '').includes('movie') || String(tile.media_type || '').includes('video')) ? 'Movie' : 'View')) }}",
                                            classes="seurat-panel-kind",
                                        )

                                    with html.Div(
                                        classes="seurat-panel-content",
                                    ):
                                        with vuetify.Template(v_if="tile.media_type === 'plot1d'"):
                                            html.Div(
                                                classes="seurat-plot1d",
                                                raw_attrs=[
                                                    ':data-plot="JSON.stringify(tile.plot || {})"',
                                                    ':data-plot-settings="JSON.stringify(tile.plot_settings || {})"',
                                                ],
                                                style=(
                                                    "display:block;"
                                                    "width:100%;"
                                                    "height:100%;"
                                                    "background:#fff;"
                                                ),
                                            )
                                            with vuetify.Template(
                                                v_if=(
                                                    "tile.plot"
                                                    " && tile.plot.series"
                                                    " && tile.plot.series.length > 1"
                                                ),
                                            ):
                                                with html.Div(classes="seurat-plot-legend"):
                                                    with vuetify.Template(
                                                        v_for="(item, j) in ((tile.plot && tile.plot.series) || [])",
                                                        key="j",
                                                    ):
                                                        with html.Div(
                                                            classes="seurat-plot-legend-item",
                                                            raw_attrs=[
                                                                ':title="item.source_label || item.source_key || (\'Series \' + (j + 1))"',
                                                            ],
                                                        ):
                                                            html.Div(
                                                                classes="seurat-plot-legend-line",
                                                                raw_attrs=[
                                                                    ":data-line-style=\"(((tile.plot_settings && tile.plot_settings.series_styles && tile.plot_settings.series_styles[(item.source_key || item.source_label || ('series:' + j))] && tile.plot_settings.series_styles[(item.source_key || item.source_label || ('series:' + j))].line_style) || item.line_style || 'solid').toLowerCase().replace('_', '-'))\"",
                                                                    ":style=\"{'--seurat-legend-color': ((tile.plot_settings && tile.plot_settings.series_styles && tile.plot_settings.series_styles[(item.source_key || item.source_label || ('series:' + j))] && tile.plot_settings.series_styles[(item.source_key || item.source_label || ('series:' + j))].color) || (tile.plot_settings && tile.plot_settings.series_colors && tile.plot_settings.series_colors[(item.source_key || item.source_label || ('series:' + j))]) || item.color || '#1565c0')}\"",
                                                                ],
                                                            )
                                                            html.Span(
                                                                "{{ item.source_label || item.source_key || ('Series ' + (j + 1)) }}",
                                                                classes="seurat-plot-legend-label",
                                                            )
                                        with vuetify.Template(v_if="tile.media_type !== 'plot1d'"):
                                            with vuetify.Template(v_if="tile.src"):
                                                with vuetify.Template(
                                                    v_if=(
                                                        "(tile.media_type === 'image' || tile.media_type === 'image_sequence')"
                                                        " && (tile.variable_type === 'scalarField'"
                                                        " || tile.payload_type === 'SCALAR_FIELD'"
                                                        " || tile.visualization_item_type === 'SCALAR_FIELD')"
                                                    )
                                                ):
                                                    with html.Div(classes="seurat-scalar-field-view"):
                                                        with html.Div(
                                                            classes="seurat-scalar-field-plot-frame seurat-panzoom-viewport",
                                                            raw_attrs=[
                                                                ":class=\"{ 'seurat-scalar-field-show-axes': tile.scalar_field_settings && tile.scalar_field_settings.show_axes }\"",
                                                            ],
                                                        ):
                                                            with html.Div(classes="seurat-panzoom-content"):
                                                                with vuetify.Template(v_if="tile.media_type === 'image_sequence'"):
                                                                    html.Img(
                                                                        src=("tile.src",),
                                                                        class_="seurat-grid-image-sequence",
                                                                        raw_attrs=[
                                                                            'data-grid-image-sequence="1"',
                                                                            ':data-fps="tile.fps || 2"',
                                                                            ':data-frame-count="tile.frame_count || 0"',
                                                                            ':data-frame-indices="(tile.frame_indices || []).join(\',\')"',
                                                                            ':data-frame-sources="JSON.stringify(tile.frame_sources || [])"',
                                                                            ':data-time-values="(tile.time_values || []).join(\',\')"',
                                                                            ':data-time-mode="tile.time_mode || \'timestep\'"',
                                                                            'data-current-frame="0"',
                                                                            'draggable="false"',
                                                                        ],
                                                                    )
                                                                with vuetify.Template(v_if="tile.media_type === 'image'"):
                                                                    html.Img(src=("tile.src",), raw_attrs=['draggable="false"'])
                                                        with vuetify.Template(
                                                            v_if=(
                                                                "tile.scalar_field_settings"
                                                                " && tile.scalar_field_settings.show_colorbar"
                                                            )
                                                        ):
                                                            with html.Div(classes="seurat-scalar-field-colorbar"):
                                                                html.Div(
                                                                    classes="seurat-scalar-field-colorbar-ramp",
                                                                    raw_attrs=[
                                                                        ":style=\"{ '--seurat-scalar-field-colorbar': ((tile.scalar_field_settings && tile.scalar_field_settings.colorbar_gradient) || 'linear-gradient(to top, #440154, #fde725)') }\"",
                                                                    ],
                                                                )
                                                                with html.Div(classes="seurat-scalar-field-colorbar-labels"):
                                                                    html.Div(
                                                                        "{{ tile.scalar_field_colorbar_max || tile.max || '' }}",
                                                                        classes="seurat-scalar-field-colorbar-label",
                                                                        raw_attrs=[
                                                                            ':title="String(tile.scalar_field_colorbar_max || tile.max || \'\')"',
                                                                        ],
                                                                    )
                                                                    html.Div(
                                                                        "{{ tile.scalar_field_colorbar_min || tile.min || '' }}",
                                                                        classes="seurat-scalar-field-colorbar-label",
                                                                        raw_attrs=[
                                                                            ':title="String(tile.scalar_field_colorbar_min || tile.min || \'\')"',
                                                                        ],
                                                                    )
                                                with vuetify.Template(
                                                    v_if=(
                                                        "tile.media_type === 'image_sequence'"
                                                        " && !(tile.variable_type === 'scalarField'"
                                                        " || tile.payload_type === 'SCALAR_FIELD'"
                                                        " || tile.visualization_item_type === 'SCALAR_FIELD')"
                                                    )
                                                ):
                                                    with html.Div(classes="seurat-panzoom-viewport"):
                                                        with html.Div(classes="seurat-panzoom-content"):
                                                            html.Img(
                                                                src=("tile.src",),
                                                                class_="seurat-grid-image-sequence",
                                                                raw_attrs=[
                                                                    'data-grid-image-sequence="1"',
                                                                    ':data-fps="tile.fps || 2"',
                                                                    ':data-frame-count="tile.frame_count || 0"',
                                                                    ':data-frame-indices="(tile.frame_indices || []).join(\',\')"',
                                                                    ':data-frame-sources="JSON.stringify(tile.frame_sources || [])"',
                                                                    ':data-time-values="(tile.time_values || []).join(\',\')"',
                                                                    ':data-time-mode="tile.time_mode || \'timestep\'"',
                                                                    'data-current-frame="0"',
                                                                    'draggable="false"',
                                                                ],
                                                                style=(
                                                                    "display:block;"
                                                                    "width:100%;"
                                                                    "height:100%;"
                                                                    "object-fit:contain;"
                                                                    "background:#111;"
                                                                ),
                                                            )
                                                with vuetify.Template(
                                                    v_if=(
                                                        "tile.media_type === 'image'"
                                                        " && !(tile.variable_type === 'scalarField'"
                                                        " || tile.payload_type === 'SCALAR_FIELD'"
                                                        " || tile.visualization_item_type === 'SCALAR_FIELD')"
                                                    )
                                                ):
                                                    with html.Div(classes="seurat-panzoom-viewport"):
                                                        with html.Div(classes="seurat-panzoom-content"):
                                                            html.Img(
                                                                src=("tile.src",),
                                                                raw_attrs=['draggable="false"'],
                                                                style=(
                                                                    "display:block;"
                                                                    "width:100%;"
                                                                    "height:100%;"
                                                                    "object-fit:contain;"
                                                                    "background:#111;"
                                                                ),
                                                            )
                                                with vuetify.Template(v_if="tile.media_type !== 'image' && tile.media_type !== 'image_sequence'"):
                                                    with html.Div(classes="seurat-panzoom-viewport"):
                                                        with html.Div(classes="seurat-panzoom-content"):
                                                            html.Video(
                                                                src=("tile.src",),
                                                                class_="seurat-grid-video",
                                                                controls=False,
                                                                autoplay=False,
                                                                loop=False,
                                                                muted=True,
                                                                raw_attrs=[
                                                                    'data-grid-video="1"',
                                                                    ':data-fps="tile.fps || 2"',
                                                                    ':data-frame-count="tile.frame_count || 0"',
                                                                    ':data-frame-indices="(tile.frame_indices || []).join(\',\')"',
                                                                    ':data-time-values="(tile.time_values || []).join(\',\')"',
                                                                    ':data-time-mode="tile.time_mode || \'timestep\'"',
                                                                    "playsinline",
                                                                    "webkit-playsinline",
                                                                ],
                                                                style=(
                                                                    "display:block;"
                                                                    "width:100%;"
                                                                    "height:100%;"
                                                                    "object-fit:contain;"
                                                                    "background:#111;"
                                                                ),
                                                            )
                                            with vuetify.Template(v_if="!tile.src"):
                                                html.Div(
                                                    "{{ tile.note ? tile.note : 'No movie src' }}",
                                                    class_="text-caption",
                                                    style=(
                                                        "display:flex;"
                                                        "height:100%;"
                                                        "align-items:center;"
                                                        "justify-content:center;"
                                                        "text-align:center;"
                                                        "padding:8px;"
                                                        "color:#ddd;"
                                                    ),
                                                )
                                with vuetify.Template(v_if="!(tile && tile.variable_name)"):
                                    with html.Div(classes="seurat-empty-cell"):
                                        vuetify.VIcon(
                                            "mdi-cursor-move",
                                            size=28,
                                            classes="seurat-empty-icon",
                                        )
                                        html.Div(
                                            "Drag a variable here",
                                            classes="seurat-empty-title",
                                        )
                                        html.Div(
                                            "Select a variable, then drag it into this panel",
                                            classes="seurat-empty-hint",
                                        )

            with vuetify.Template(v_if="detailsSelectedVar"):
                with vuetify.VCard(
                    variant="flat",
                    classes="seurat-inspector-card",
                ):
                    with vuetify.VCardText(classes="seurat-inspector-content"):
                        with html.Div(classes="seurat-inspector-row"):
                            with html.Div(classes="seurat-inspector-identity"):
                                html.Div("Selected variable", classes="seurat-inspector-label")
                                html.Div(
                                    "{{ detailsSelectedVar }}",
                                    classes="seurat-inspector-value seurat-inspector-variable",
                                )
                            vuetify.VBtn(
                                "{{ detailsNumSources + ' sources' }}",
                                prepend_icon="mdi-database-outline",
                                variant="tonal",
                                size="small",
                                click=ctrl.toggle_sources,
                                classes="seurat-inspector-sources",
                            )
                            with html.Div(classes="seurat-inspector-stat"):
                                html.Div("Global", classes="seurat-inspector-label")
                                html.Div(
                                    "{{ detailsGlobalMin + ' / ' + detailsGlobalMax }}",
                                    classes="seurat-inspector-value",
                                )
                            with html.Div(classes="seurat-inspector-stat"):
                                html.Div("Median", classes="seurat-inspector-label")
                                html.Div(
                                    "{{ detailsMedianMin + ' / ' + detailsMedianMax }}",
                                    classes="seurat-inspector-value",
                                )
                            with html.Div(classes="seurat-inspector-stat"):
                                html.Div("Mean", classes="seurat-inspector-label")
                                html.Div(
                                    "{{ detailsMeanMin + ' / ' + detailsMeanMax }}",
                                    classes="seurat-inspector-value",
                                )
                            with html.Div(classes="seurat-inspector-query"):
                                html.Div("Query view", classes="seurat-inspector-label")
                                html.Div(
                                    "{{ queryViewLabel }}",
                                    classes="seurat-inspector-value",
                                    title=("queryViewLabel",),
                                )
                            vuetify.VBtn(
                                icon="mdi-close",
                                variant="text",
                                size="x-small",
                                click=(ctrl.pick_var, "[detailsSelectedVar]"),
                                title="Close inspector",
                                classes="seurat-inspector-close",
                            )
            self.source_dialog.build()
            self.scalar_plot_dialog.build()
            self.plot_settings_panel.build()
            self.plugin_options_panel.build()
            self.scalar_field_settings_panel.build()
