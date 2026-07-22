"""Visualization grid and layout controls."""

from trame.app import TrameComponent
from trame.widgets import html
from trame.widgets import vuetify3 as vuetify

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
            html.Button(
                "⚙",
                classes="seurat-toolbar-menu-btn seurat-toolbar-icon-btn",
                raw_attrs=[
                    'type="button"',
                    'aria-label="Settings"',
                ],
                title="Settings",
            )
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
        self.source_dialog = SourceDialog(server)
        self.scalar_plot_dialog = ScalarPlotDialog(server)
        self.plot_settings_panel = PlotSettingsPanel(server)
        self.plugin_options_panel = PluginOptionsPanel(server)
        self.scalar_field_settings_panel = ScalarFieldSettingsPanel(server)

    def build(self):
        ctrl = self.ctrl
        with vuetify.VCol(
            classes="seurat-content-column",
            style="display:flex; flex-direction:column; height:80vh;",
        ):
            with vuetify.VCard(
                variant="outlined",
                style="flex:1 1 auto; min-height:0; display:flex; flex-direction:column;",
            ):
                with vuetify.VCardText(
                    style=(
                        "height:100%;"
                        "min-height:0;"
                        "display:flex;"
                        "flex-direction:column;"
                        "overflow:hidden;"
                    ),
                ):
                    with html.Div(classes="seurat-vcr-bar seurat-grid-controls-header"):
                        with html.Div(classes="seurat-vcr-controls"):
                            html.Button(
                                "|<",
                                classes="seurat-vcr-btn",
                                raw_attrs=[
                                    'type="button"',
                                    'data-vcr-action="start"',
                                ],
                                title="Jump to start",
                            )
                            html.Button(
                                "<<",
                                classes="seurat-vcr-btn",
                                raw_attrs=[
                                    'type="button"',
                                    'data-vcr-action="back"',
                                ],
                                title="Back step",
                            )
                            html.Button(
                                "▶",
                                classes="seurat-vcr-btn",
                                raw_attrs=[
                                    'type="button"',
                                    'data-vcr-action="play"',
                                ],
                                title="Play all",
                            )
                            html.Button(
                                "⏸",
                                classes="seurat-vcr-btn",
                                raw_attrs=[
                                    'type="button"',
                                    'data-vcr-action="pause"',
                                ],
                                title="Pause all",
                            )
                            html.Button(
                                ">>",
                                classes="seurat-vcr-btn",
                                raw_attrs=[
                                    'type="button"',
                                    'data-vcr-action="forward"',
                                ],
                                title="Forward step",
                            )
                            html.Button(
                                ">|",
                                classes="seurat-vcr-btn",
                                raw_attrs=[
                                    'type="button"',
                                    'data-vcr-action="end"',
                                ],
                                title="Jump to end",
                            )
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
                            " + 'margin:4px 0 0 0;'"
                            " + 'border:1px solid #cfcfcf;')",
                        ),
                    ):
                        with vuetify.Template(v_for="(tile, i) in gridCells", key="i"):
                            with html.Div(
                                click=(
                                    ctrl.set_active_grid_cell,
                                    "[i, (($event && $event.target && $event.target.closest && $event.target.closest('.seurat-cell-close, .seurat-timeline-driver-btn, .seurat-grid-track-resize-handle')) ? 1 : 0), (($event && $event.shiftKey) ? 1 : 0)]",
                                ),
                                classes="seurat-dropcell",
                                raw_attrs=[
                                    ':data-cell-index="i"',
                                    ':data-cell-filled="((tile && tile.variable_name) ? 1 : 0)"',
                                    ':data-timeline-driver="(timelineDriverCell === i ? 1 : 0)"',
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
                                    " + ((gridLayoutMode === 'spanning') ? 'border:1px solid #cfcfcf;' : ('border-left:1px solid #cfcfcf; border-top:1px solid #cfcfcf;'"
                                    " + (((i % gridCols) === (gridCols - 1)) ? 'border-right:1px solid #cfcfcf;' : '')"
                                    " + ((i >= ((gridRows - 1) * gridCols)) ? 'border-bottom:1px solid #cfcfcf;' : '')))"
                                    " + ((activeGridCell === i) ? 'background:#e7f0ff; outline:3px solid #0d47a1; outline-offset:-3px; z-index:2;' : '')"
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
                                        style=(
                                            "'display:flex;'"
                                            " + 'align-items:center;'"
                                            " + 'gap:8px;'"
                                            " + 'width:100%;'"
                                            " + 'height:32px;'"
                                            " + 'padding:4px 6px;'"
                                            " + (((selectedGridCellMap || {})[String(i)]) ? 'background:#ef6c00; color:#fff; border-bottom:1px solid #b53d00;' : ((activeGridCell === i) ? 'background:#1565c0; color:#fff; border-bottom:1px solid #0d47a1;' : 'background:#7bd0ef; color:#111; border-bottom:1px solid #3ca7c9;'))",
                                        ),
                                    ):
                                        html.Div(
                                            "{{ tile.display_title || tile.variable_name || 'variable' }}",
                                            style="flex:1 1 auto; min-width:0; font-size:0.9rem; font-weight:400; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;",
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
                                            ],
                                            title="Use as timeline driver",
                                        ):
                                            html.Span(
                                                classes="seurat-timeline-clock-icon",
                                                raw_attrs=['aria-hidden="true"'],
                                            )
                                        html.Button(
                                            "x",
                                            classes="seurat-cell-close",
                                            click=(ctrl.clear_grid_cell, "[i]"),
                                            style=(
                                                "margin-left:auto;"
                                                "flex:0 0 auto;"
                                                "width:18px;"
                                                "height:18px;"
                                                "line-height:16px;"
                                                "padding:0;"
                                                "font-size:11px;"
                                                "border:1px solid #2c7c97;"
                                                "border-radius:2px;"
                                                "background:#fff;"
                                                "color:#222;"
                                                "cursor:pointer;"
                                            ),
                                            title="Remove",
                                        )

                                    with html.Div(
                                        style="width:100%; flex:1 1 auto; min-height:0; background:#111; position:relative; overflow:hidden;",
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
                                        html.Div("+", classes="seurat-empty-plus")
                                        html.Div("Drop variable here", classes="seurat-empty-hover-label")

            html.Div(style="height: 8px; flex:0 0 auto;")

            with vuetify.VCard(variant="outlined", style="flex:0 0 auto;"):
                with vuetify.VCardText(class_="py-2"):
                    with vuetify.Template(v_if="detailsSelectedVar"):
                        with html.Div(style="display:flex; align-items:center; gap:12px; width:100%;"):
                            html.Div("{{ 'Details: ' + detailsSelectedVar }}", class_="text-body-2")
                            vuetify.VBtn(
                                "{{ 'SOURCES(' + detailsNumSources + ')' }}",
                                variant="tonal",
                                size="small",
                                click=ctrl.toggle_sources,
                            )
                            with html.Div(
                                class_="text-caption",
                                style="display:flex; align-items:center; gap:12px; white-space:nowrap;",
                            ):
                                html.Span("Min/Max")
                                with html.Span():
                                    html.Strong("Global ")
                                    html.Span("{{ detailsGlobalMin + ' / ' + detailsGlobalMax }}")
                                with html.Span():
                                    html.Strong("Median ")
                                    html.Span("{{ detailsMedianMin + ' / ' + detailsMedianMax }}")
                                with html.Span():
                                    html.Strong("Mean ")
                                    html.Span("{{ detailsMeanMin + ' / ' + detailsMeanMax }}")
                            vuetify.VSpacer()
                            html.Div("{{ 'QueryView: ' + queryViewLabel }}", class_="text-caption")
                    with vuetify.Template(v_if="!detailsSelectedVar"):
                        html.Div("Select a variable", class_="text-caption")
            self.source_dialog.build()
            self.scalar_plot_dialog.build()
            self.plot_settings_panel.build()
            self.plugin_options_panel.build()
            self.scalar_field_settings_panel.build()
