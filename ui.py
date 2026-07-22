from trame.ui.vuetify3 import SinglePageLayout
from trame.widgets import html
from trame.widgets import vuetify3 as vuetify

from db import SCALAR_FIELD_COLORMAP_OPTIONS


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


def build_ui(server, refresh_variable_list, campaign_name: str = ""):
    state, ctrl = server.state, server.controller
    with SinglePageLayout(server) as layout:
        layout.title.set_text(
            f"Campaign loaded: {campaign_name}" if campaign_name else "Campaign loaded"
        )

        with layout.toolbar:
            html.Span("Query:", class_="text-caption ml-4")
            vuetify.VBtn(
                "?",
                click=ctrl.show_query_help,
                variant="tonal",
                size="small",
                min_width=32,
                title="Query help",
            )
            vuetify.VTextField(
                v_model=("queryText",),
                placeholder="e.g. var == 'rho' and source_dataset == 'hll_128/output.bp'",
                density="compact",
                hide_details=True,
                variant="outlined",
                style="max-width: 420px;",
                class_="mx-2",
            )
            vuetify.VBtn("Query", click=ctrl.run_query, variant="outlined", size="small")
            vuetify.VBtn("Clear", click=ctrl.clear_query, variant="text", size="small", class_="ml-1")
            with vuetify.Template(v_if="queryError"):
                html.Span("{{ queryError }}", class_="text-caption ml-2", style="color:#b00020;")

        with layout.content:
            with vuetify.VDialog(v_model=("showHelpModal",), max_width="520"):
                with vuetify.VCard():
                    with vuetify.VCardTitle():
                        with html.Div(style="display:flex; align-items:center; gap:8px; width:100%;"):
                            html.Div("{{ helpModalTitle || 'Help' }}")
                            vuetify.VSpacer()
                            vuetify.VBtn("Close", variant="text", size="small", click=ctrl.close_help_modal)
                    with vuetify.VCardText():
                        vuetify.VTextarea(
                            v_model=("helpModalText",),
                            readonly=True,
                            auto_grow=True,
                            rows=3,
                            variant="outlined",
                            hide_details=True,
                        )
            with vuetify.VContainer(fluid=True, class_="pa-2"):
                html.Div(
                    "",
                    id="seurat-reset-view-request",
                    style="display:none;",
                    raw_attrs=[':data-reset-view-request="JSON.stringify(resetViewRequest || {})"'],
                )
                with vuetify.VRow(classes="seurat-main-row", no_gutters=True):
                    with vuetify.VCol(
                        id="seurat-variable-column",
                        classes="seurat-variable-column",
                        style="display:flex; flex-direction:column; height:80vh;",
                    ):
                        with vuetify.VCard(
                            variant="outlined",
                            style="flex:1 1 auto; min-height:0; display:flex; flex-direction:column;",
                        ):
                            with vuetify.VCardTitle():
                                html.Div("Variables")
                            with vuetify.VCardText(style="flex:1 1 auto; min-height:0; overflow-y:auto;"):
                                with html.Div(
                                    style="display:flex; align-items:center; gap:8px; padding:0 4px 8px 4px;",
                                ):
                                    html.Span("Group by:", class_="text-caption")
                                    with vuetify.VBtnToggle(
                                        v_model=("variablePaneView",),
                                        mandatory=True,
                                        density="compact",
                                        divided=True,
                                        variant="outlined",
                                    ):
                                        vuetify.VBtn("Variable", value="variables", size="small")
                                        vuetify.VBtn("File", value="files", size="small")
                                with html.Div(style="padding:0 4px 8px 4px;"):
                                    vuetify.VCheckbox(
                                        v_model=("showOnlyVisualizedVars",),
                                        label="Only with visualizations",
                                        density="compact",
                                        hide_details=True,
                                    )
                                with vuetify.VList(density="compact", class_="seurat-var-list"):
                                    html.Div(
                                        "No variables",
                                        v_if="!(variableGroups || []).length",
                                        class_="text-caption",
                                        style="padding:8px 10px; color:#777;",
                                    )
                                    with vuetify.Template(v_for="group in variableGroups", key="group.name"):
                                        with html.Div(
                                            class_="seurat-var-group",
                                            style=(
                                                "border:1px solid #b8c4d1;"
                                                "background:#f4f7fa;"
                                                "box-shadow: inset 0 0 0 1px #e2e8ef;"
                                            ),
                                        ):
                                            with html.Button(
                                                class_="seurat-var-group-title",
                                                click=(ctrl.toggle_variable_group, "[group.name]"),
                                                style="font-weight:800;",
                                                raw_attrs=[
                                                    'type="button"',
                                                    ':aria-expanded="!(variableGroupCollapsed && variableGroupCollapsed[group.name])"',
                                                ],
                                            ):
                                                html.Span(
                                                    "{{ (variableGroupCollapsed && variableGroupCollapsed[group.name]) ? '▸' : '▾' }}",
                                                    class_="seurat-var-group-chevron",
                                                )
                                                html.Span(
                                                    "{{ group.name + (((group.file_count || 0) > 1) ? (' (' + group.file_count + ')') : '') }}",
                                                    raw_attrs=[':title="group.name"'],
                                                    style="flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;",
                                                )
                                            with html.Div(v_if="!(variableGroupCollapsed && variableGroupCollapsed[group.name])"):
                                                with vuetify.Template(v_for="v in group.variables", key="group.name + '::' + v.id"):
                                                    with html.Div(
                                                        click=(ctrl.pick_var, "[v.id]"),
                                                        draggable="true",
                                                        classes="seurat-draggable-var seurat-var-item",
                                                        raw_attrs=[':data-item="v.id"', ':title="v.path || v.id"'],
                                                        style=(
                                                            "((v.id === selectedVar) ? 'background:#dfe7ef; box-shadow: inset 0 0 0 1px #b9c8d7;' : '')",
                                                        ),
                                                    ):
                                                        html.Span("{{ v.label || v.name || v.id }}")

                    html.Div(
                        classes="seurat-variable-resizer",
                        raw_attrs=[
                            "data-variable-panel-resizer",
                            'role="separator"',
                            'aria-label="Resize variable list"',
                            'aria-orientation="vertical"',
                            'aria-valuemin="180"',
                            'tabindex="0"',
                        ],
                        title="Drag to resize the variable list",
                    )

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
                                        "Time = 0.000000",
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

                        with vuetify.VDialog(v_model=("showSourcesModal",), max_width="1200"):
                            with vuetify.VCard():
                                with vuetify.VCardTitle():
                                    with html.Div(style="display:flex; align-items:center; gap:8px; width:100%;"):
                                        html.Div("{{ sourceDialogTitle || 'Sources' }}")
                                        vuetify.VSpacer()
                                        vuetify.VBtn("Close", variant="text", size="small", click=ctrl.cancel_source_dialog)

                                with vuetify.VCardText():
                                    with vuetify.Template(v_if="detailsSelectedVar"):
                                        with html.Div(
                                            style=(
                                                "display:flex;"
                                                "align-items:center;"
                                                "gap:8px;"
                                                "margin-bottom:8px;"
                                            )
                                        ):
                                            html.Span(
                                                "Filter Sources:",
                                                class_="text-caption",
                                                style="white-space:nowrap;",
                                            )
                                            vuetify.VBtn(
                                                "?",
                                                variant="tonal",
                                                size="small",
                                                min_width=32,
                                                title="Source filter help",
                                                click=ctrl.show_source_filter_help,
                                            )
                                            vuetify.VTextField(
                                                v_model=("sourceFilterDraftText",),
                                                placeholder="e.g. contains(producer, 'F0.03968') and min > 0.32",
                                                density="compact",
                                                hide_details=True,
                                                variant="outlined",
                                                style="max-width:620px; min-width:360px;",
                                            )
                                            vuetify.VBtn(
                                                "Filter",
                                                variant="tonal",
                                                size="small",
                                                click=ctrl.apply_source_dialog_filter,
                                            )
                                            with vuetify.Template(v_if="sourceDialogMode === 'add'"):
                                                vuetify.VBtn(
                                                    "Select All",
                                                    variant="tonal",
                                                    size="small",
                                                    click=ctrl.select_all_sources,
                                                )
                                                vuetify.VBtn(
                                                    "Clear All",
                                                    variant="text",
                                                    size="small",
                                                    click=ctrl.clear_all_sources,
                                                )
                                        with vuetify.Template(v_if="sourceFilterError"):
                                            html.Div("{{ sourceFilterError }}", class_="text-caption mb-2", style="color:#b00020;")
                                        with vuetify.Template(v_if="sourceDialogStatus && sourceDialogStatusIsError"):
                                            html.Div("{{ sourceDialogStatus }}", class_="text-caption mb-2", style="color:#b00020;")
                                        with vuetify.Template(v_if="sourceDialogStatus && !sourceDialogStatusIsError"):
                                            html.Div("{{ sourceDialogStatus }}", class_="text-caption mb-2", style="color:#2e7d32;")
                                        html.Div(
                                            "{{ ((sourceDialogMode === 'add') ? 'Selected sources: ' : 'Selected source: ') + selectedSourceLabel }}",
                                            class_="text-caption mb-2",
                                        )
                                        with html.Div(
                                            style=(
                                                "max-height:60vh;"
                                                "overflow-y:auto;"
                                                "overflow-x:scroll;"
                                                "white-space:nowrap;"
                                                "scrollbar-gutter:stable;"
                                            )
                                        ):
                                            with vuetify.VTable(density="compact"):
                                                with html.Thead():
                                                    with html.Tr():
                                                        with html.Th(
                                                            style="cursor:pointer; user-select:none; white-space:nowrap; width:72px;",
                                                            click=(ctrl.sort_sources, "['show']"),
                                                        ):
                                                            html.Span("Selected")
                                                            with vuetify.Template(v_if="sourceSortField === 'show'"):
                                                                vuetify.VIcon(
                                                                    ("sourceSortAsc ? 'mdi-arrow-up' : 'mdi-arrow-down'",),
                                                                    size="x-small",
                                                                    class_="ml-1",
                                                                )
                                                            with vuetify.Template(v_if="sourceSortField !== 'show'"):
                                                                vuetify.VIcon("mdi-sort", size="x-small", class_="ml-1")
                                                        with html.Th(
                                                            style="cursor:pointer; user-select:none; white-space:nowrap;",
                                                            click=(ctrl.sort_sources, "['source_dataset']"),
                                                        ):
                                                            html.Span("source dataset")
                                                            with vuetify.Template(v_if="sourceSortField === 'source_dataset'"):
                                                                vuetify.VIcon(
                                                                    ("sourceSortAsc ? 'mdi-arrow-up' : 'mdi-arrow-down'",),
                                                                    size="x-small",
                                                                    class_="ml-1",
                                                                )
                                                            with vuetify.Template(v_if="sourceSortField !== 'source_dataset'"):
                                                                vuetify.VIcon("mdi-sort", size="x-small", class_="ml-1")

                                                        with html.Th(
                                                            style="cursor:pointer; user-select:none; white-space:nowrap;",
                                                            click=(ctrl.sort_sources, "['min']"),
                                                        ):
                                                            html.Span("min")
                                                            with vuetify.Template(v_if="sourceSortField === 'min'"):
                                                                vuetify.VIcon(
                                                                    ("sourceSortAsc ? 'mdi-arrow-up' : 'mdi-arrow-down'",),
                                                                    size="x-small",
                                                                    class_="ml-1",
                                                                )
                                                            with vuetify.Template(v_if="sourceSortField !== 'min'"):
                                                                vuetify.VIcon("mdi-sort", size="x-small", class_="ml-1")

                                                        with html.Th(
                                                            style="cursor:pointer; user-select:none; white-space:nowrap;",
                                                            click=(ctrl.sort_sources, "['max']"),
                                                        ):
                                                            html.Span("max")
                                                            with vuetify.Template(v_if="sourceSortField === 'max'"):
                                                                vuetify.VIcon(
                                                                    ("sourceSortAsc ? 'mdi-arrow-up' : 'mdi-arrow-down'",),
                                                                    size="x-small",
                                                                    class_="ml-1",
                                                                )
                                                            with vuetify.Template(v_if="sourceSortField !== 'max'"):
                                                                vuetify.VIcon("mdi-sort", size="x-small", class_="ml-1")
                                                with html.Tbody():
                                                    with vuetify.Template(v_for="(r, i) in sourceRows", key="i"):
                                                        with html.Tr(
                                                            style=(
                                                                "((selectedSourceKeys || []).includes(r._key)) ? "
                                                                "'background-color:#f5f5f5; cursor:pointer;' : "
                                                                "'cursor:pointer;'",
                                                            ),
                                                            click=(ctrl.source_dialog_select, "[r._key]"),
                                                        ):
                                                            with html.Td(style="text-align:center; white-space:nowrap;"):
                                                                with vuetify.Template(v_if="sourceDialogMode === 'add'"):
                                                                    html.Input(
                                                                        type="checkbox",
                                                                        checked=("((selectedSourceKeys || []).includes(r._key))",),
                                                                    )
                                                                with vuetify.Template(v_if="sourceDialogMode !== 'add'"):
                                                                    html.Input(
                                                                        type="radio",
                                                                        name="selected-source",
                                                                        checked=("((selectedSourceKeys || []).includes(r._key))",),
                                                                    )
                                                            html.Td(
                                                                "{{ r.sourceName || r.source_label || r.source_dataset || [r.producer, r.casename, r.file].filter(Boolean).join('/') }}",
                                                                style="white-space:nowrap;",
                                                            )
                                                            html.Td("{{ r.min }}", style="white-space:nowrap;")
                                                            html.Td("{{ r.max }}", style="white-space:nowrap;")
                                        with vuetify.Template(v_if="!detailsSelectedVar"):
                                            html.Div("Select a variable first.", class_="text-caption")
                                with vuetify.VCardActions():
                                    vuetify.VSpacer()
                                    vuetify.VBtn("Cancel", variant="text", click=ctrl.cancel_source_dialog)
                                    vuetify.VBtn("Apply", variant="tonal", click=ctrl.apply_source_dialog)

                        with vuetify.VDialog(v_model=("showScalarPlotDialog",), max_width="560"):
                            with vuetify.VCard():
                                vuetify.VCardTitle("Generate Scalar Plot")
                                with vuetify.VCardText():
                                    html.Div("{{ scalarPlotDialogMessage }}", class_="text-body-2")
                                    vuetify.VCheckbox(
                                        v_model=("scalarPlotAlwaysForSession",),
                                        label="Always generate scalar plots for this session",
                                        density="compact",
                                        hide_details=True,
                                        class_="mt-3",
                                    )
                                with vuetify.VCardActions():
                                    vuetify.VSpacer()
                                    vuetify.VBtn(
                                        "Cancel",
                                        variant="text",
                                        click=ctrl.cancel_scalar_plot_generation,
                                    )
                                    vuetify.VBtn(
                                        "Generate",
                                        variant="tonal",
                                        click=ctrl.confirm_scalar_plot_generation,
                                    )

                        with html.Div(
                            id="seurat-plot-settings-panel",
                            v_show=("showPlotSettingsModal",),
                            classes="seurat-floating-options-panel seurat-plot-settings-panel",
                        ):
                            with vuetify.VCard(classes="seurat-floating-options-card", elevation=6):
                                with vuetify.VCardTitle(classes="seurat-floating-options-titlebar"):
                                    with html.Div(style="display:flex; align-items:center; gap:8px; width:100%;"):
                                        html.Div(
                                            "{{ 'Plot Settings: ' + (plotSettingsTitle || '') }}",
                                            classes="seurat-floating-panel-drag-handle",
                                        )
                                        vuetify.VSpacer()
                                        vuetify.VBtn("Close", variant="text", size="small", click=ctrl.cancel_plot_settings)

                                with vuetify.VCardText(classes="seurat-floating-options-content"):
                                    with vuetify.Template(v_if="plotSettingsStatus"):
                                        html.Div("{{ plotSettingsStatus }}", class_="text-caption mb-2", style="color:#b00020;")

                                    html.Div("Grid", classes="seurat-plot-settings-section-title")
                                    with html.Div(classes="seurat-plot-settings-section"):
                                        with html.Div(classes="seurat-plot-settings-grid-controls"):
                                            with html.Div(classes="seurat-plot-settings-background-control"):
                                                html.Span("Background", class_="text-caption")
                                                with html.Div(classes="seurat-plot-settings-color-menu"):
                                                    html.Button(
                                                        "",
                                                        classes="seurat-plot-settings-current-color",
                                                        raw_attrs=[
                                                            'type="button"',
                                                            ':title="\'Background: \' + (plotSettingsBackgroundColor || \'\')"',
                                                            ':style="{ backgroundColor: plotSettingsBackgroundColor || \'#ffffff\' }"',
                                                        ],
                                                    )
                                                    with vuetify.VMenu(
                                                        activator="parent",
                                                        location="bottom end",
                                                        close_on_content_click=False,
                                                    ):
                                                        with vuetify.VCard(classes="seurat-plot-settings-color-popup", elevation=4):
                                                            with vuetify.VCardText(class_="pa-2"):
                                                                html.Div("Standard Colors", classes="text-caption seurat-plot-settings-popup-title")
                                                                with html.Div(classes="seurat-plot-settings-standard-colors"):
                                                                    with vuetify.Template(
                                                                        v_for="color in plotSettingsStandardColors",
                                                                        key="'background:' + color",
                                                                    ):
                                                                        html.Button(
                                                                            "",
                                                                            classes="seurat-plot-settings-color-swatch",
                                                                            raw_attrs=[
                                                                                'type="button"',
                                                                                ':title="color"',
                                                                                ':style="{ backgroundColor: color, boxShadow: ((plotSettingsBackgroundColor || \'\').toLowerCase() === color.toLowerCase()) ? \'0 0 0 2px #111\' : \'none\' }"',
                                                                            ],
                                                                            click=(ctrl.update_plot_background_color, "[color]"),
                                                                        )
                                                                html.Div("More colors...", classes="text-caption seurat-plot-settings-more-colors")
                                                                vuetify.VColorPicker(
                                                                    hide_header=True,
                                                                    hide_inputs=False,
                                                                    show_swatches=False,
                                                                    width=220,
                                                                    raw_attrs=[
                                                                        ':model-value="plotSettingsBackgroundColor"',
                                                                        ':modes="[\'hex\', \'rgb\', \'hsl\']"',
                                                                    ],
                                                                    update_modelValue=(ctrl.update_plot_background_color, "[$event]"),
                                                                )
                                            with html.Div(
                                                classes="seurat-plot-settings-background-control",
                                                raw_attrs=[':style="{ opacity: plotSettingsShowGrid ? 1 : 0.45 }"'],
                                            ):
                                                vuetify.VCheckbox(
                                                    v_model=("plotSettingsShowGrid",),
                                                    density="compact",
                                                    hide_details=True,
                                                    classes="seurat-plot-settings-toggle",
                                                )
                                                html.Span("Grid lines", class_="text-caption")
                                                with html.Div(classes="seurat-plot-settings-color-menu"):
                                                    html.Button(
                                                        "",
                                                        classes="seurat-plot-settings-current-color",
                                                        raw_attrs=[
                                                            'type="button"',
                                                            ':disabled="!plotSettingsShowGrid"',
                                                            ':title="\'Grid lines: \' + (plotSettingsGridColor || \'\')"',
                                                            ':style="{ backgroundColor: plotSettingsGridColor || \'#e8e8e8\', cursor: plotSettingsShowGrid ? \'pointer\' : \'not-allowed\' }"',
                                                        ],
                                                    )
                                                    with vuetify.VMenu(
                                                        activator="parent",
                                                        location="bottom end",
                                                        close_on_content_click=False,
                                                        raw_attrs=[':disabled="!plotSettingsShowGrid"'],
                                                    ):
                                                        with vuetify.VCard(classes="seurat-plot-settings-color-popup", elevation=4):
                                                            with vuetify.VCardText(class_="pa-2"):
                                                                html.Div("Standard Colors", classes="text-caption seurat-plot-settings-popup-title")
                                                                with html.Div(classes="seurat-plot-settings-standard-colors"):
                                                                    with vuetify.Template(
                                                                        v_for="color in plotSettingsStandardColors",
                                                                        key="'grid:' + color",
                                                                    ):
                                                                        html.Button(
                                                                            "",
                                                                            classes="seurat-plot-settings-color-swatch",
                                                                            raw_attrs=[
                                                                                'type="button"',
                                                                                ':disabled="!plotSettingsShowGrid"',
                                                                                ':title="color"',
                                                                                ':style="{ backgroundColor: color, boxShadow: ((plotSettingsGridColor || \'\').toLowerCase() === color.toLowerCase()) ? \'0 0 0 2px #111\' : \'none\' }"',
                                                                            ],
                                                                            click=(ctrl.update_plot_grid_color, "[color]"),
                                                                        )
                                                                html.Div("More colors...", classes="text-caption seurat-plot-settings-more-colors")
                                                                vuetify.VColorPicker(
                                                                    hide_header=True,
                                                                    hide_inputs=False,
                                                                    show_swatches=False,
                                                                    width=220,
                                                                    raw_attrs=[
                                                                        ':model-value="plotSettingsGridColor"',
                                                                        ':modes="[\'hex\', \'rgb\', \'hsl\']"',
                                                                        ':disabled="!plotSettingsShowGrid"',
                                                                    ],
                                                                    update_modelValue=(ctrl.update_plot_grid_color, "[$event]"),
                                                                )
                                            with html.Div(
                                                classes="seurat-plot-settings-background-control",
                                                raw_attrs=[':style="{ opacity: plotSettingsShowCursor ? 1 : 0.45 }"'],
                                            ):
                                                vuetify.VCheckbox(
                                                    v_model=("plotSettingsShowCursor",),
                                                    density="compact",
                                                    hide_details=True,
                                                    classes="seurat-plot-settings-toggle",
                                                )
                                                html.Span("Cursor", class_="text-caption")
                                                with html.Div(classes="seurat-plot-settings-color-menu"):
                                                    html.Button(
                                                        "",
                                                        classes="seurat-plot-settings-current-color",
                                                        raw_attrs=[
                                                            'type="button"',
                                                            ':disabled="!plotSettingsShowCursor"',
                                                            ':title="\'Cursor: \' + (plotSettingsCursorColor || \'\')"',
                                                            ':style="{ backgroundColor: plotSettingsCursorColor || \'#111111\', cursor: plotSettingsShowCursor ? \'pointer\' : \'not-allowed\' }"',
                                                        ],
                                                    )
                                                    with vuetify.VMenu(
                                                        activator="parent",
                                                        location="bottom end",
                                                        close_on_content_click=False,
                                                        raw_attrs=[':disabled="!plotSettingsShowCursor"'],
                                                    ):
                                                        with vuetify.VCard(classes="seurat-plot-settings-color-popup", elevation=4):
                                                            with vuetify.VCardText(class_="pa-2"):
                                                                html.Div("Standard Colors", classes="text-caption seurat-plot-settings-popup-title")
                                                                with html.Div(classes="seurat-plot-settings-standard-colors"):
                                                                    with vuetify.Template(
                                                                        v_for="color in plotSettingsStandardColors",
                                                                        key="'cursor:' + color",
                                                                    ):
                                                                        html.Button(
                                                                            "",
                                                                            classes="seurat-plot-settings-color-swatch",
                                                                            raw_attrs=[
                                                                                'type="button"',
                                                                                ':disabled="!plotSettingsShowCursor"',
                                                                                ':title="color"',
                                                                                ':style="{ backgroundColor: color, boxShadow: ((plotSettingsCursorColor || \'\').toLowerCase() === color.toLowerCase()) ? \'0 0 0 2px #111\' : \'none\' }"',
                                                                            ],
                                                                            click=(ctrl.update_plot_cursor_color, "[color]"),
                                                                        )
                                                                html.Div("More colors...", classes="text-caption seurat-plot-settings-more-colors")
                                                                vuetify.VColorPicker(
                                                                    hide_header=True,
                                                                    hide_inputs=False,
                                                                    show_swatches=False,
                                                                    width=220,
                                                                    raw_attrs=[
                                                                        ':model-value="plotSettingsCursorColor"',
                                                                        ':modes="[\'hex\', \'rgb\', \'hsl\']"',
                                                                        ':disabled="!plotSettingsShowCursor"',
                                                                    ],
                                                                    update_modelValue=(ctrl.update_plot_cursor_color, "[$event]"),
                                                                )

                                    html.Div("Axes", classes="seurat-plot-settings-section-title mt-3")
                                    with html.Div(classes="seurat-plot-settings-section"):
                                        with html.Div(classes="seurat-plot-settings-axis-list"):
                                            with html.Div(classes="seurat-plot-settings-axis-row"):
                                                html.Span("X:", classes="seurat-plot-settings-axis-label")
                                                vuetify.VCheckbox(
                                                    v_model=("plotSettingsXAuto",),
                                                    label="Auto range",
                                                    density="compact",
                                                    hide_details=True,
                                                )
                                                vuetify.VTextField(
                                                    v_model=("plotSettingsXMin",),
                                                    label="Min",
                                                    density="compact",
                                                    hide_details=True,
                                                    raw_attrs=[':disabled="plotSettingsXAuto"'],
                                                )
                                                vuetify.VTextField(
                                                    v_model=("plotSettingsXMax",),
                                                    label="Max",
                                                    density="compact",
                                                    hide_details=True,
                                                    raw_attrs=[':disabled="plotSettingsXAuto"'],
                                                )
                                                html.Span("Scale", class_="text-caption")
                                                with html.Select(
                                                    v_model=("plotSettingsXScale",),
                                                    classes="seurat-scalar-plot-policy",
                                                ):
                                                    html.Option("Linear", value="linear")
                                                    html.Option("Log", value="log")

                                            with html.Div(classes="seurat-plot-settings-axis-row"):
                                                html.Span("Y:", classes="seurat-plot-settings-axis-label")
                                                vuetify.VCheckbox(
                                                    v_model=("plotSettingsYAuto",),
                                                    label="Auto range",
                                                    density="compact",
                                                    hide_details=True,
                                                )
                                                vuetify.VTextField(
                                                    v_model=("plotSettingsYMin",),
                                                    label="Min",
                                                    density="compact",
                                                    hide_details=True,
                                                    raw_attrs=[':disabled="plotSettingsYAuto"'],
                                                )
                                                vuetify.VTextField(
                                                    v_model=("plotSettingsYMax",),
                                                    label="Max",
                                                    density="compact",
                                                    hide_details=True,
                                                    raw_attrs=[':disabled="plotSettingsYAuto"'],
                                                )
                                                html.Span("Scale", class_="text-caption")
                                                with html.Select(
                                                    v_model=("plotSettingsYScale",),
                                                    classes="seurat-scalar-plot-policy",
                                                ):
                                                    html.Option("Linear", value="linear")
                                                    html.Option("Log", value="log")

                                    html.Div("Curves", classes="seurat-plot-settings-section-title mt-3")
                                    with html.Div(classes="seurat-plot-settings-section"):
                                        with html.Div(classes="seurat-plot-settings-curves-layout"):
                                            with html.Div(classes="seurat-plot-settings-curve-controls"):
                                                vuetify.VTextField(
                                                    v_model=("plotSettingsLineWidth",),
                                                    label="Line width",
                                                    density="compact",
                                                    hide_details=True,
                                                    raw_attrs=['type="number"', 'min="0.5"', 'max="8"', 'step="0.5"'],
                                                    style="max-width:160px;",
                                                )
                                            with html.Div(classes="seurat-plot-settings-color-list"):
                                                with html.Div(v_if="!(plotSettingsSeriesRows || []).length", class_="text-caption"):
                                                    html.Span("No series")
                                                with vuetify.Template(v_for="row in plotSettingsSeriesRows", key="row.key"):
                                                    with html.Div(classes="seurat-plot-settings-series-row"):
                                                        with html.Div(classes="seurat-plot-settings-color-menu"):
                                                            html.Button(
                                                                "",
                                                                classes="seurat-plot-settings-current-color",
                                                                raw_attrs=[
                                                                    'type="button"',
                                                                    ':title="\'Color: \' + (row.color || \'\')"',
                                                                    ':style="{ backgroundColor: row.color || \'#1565c0\' }"',
                                                                ],
                                                            )
                                                            with vuetify.VMenu(
                                                                activator="parent",
                                                                location="bottom end",
                                                                close_on_content_click=False,
                                                            ):
                                                                with vuetify.VCard(classes="seurat-plot-settings-color-popup", elevation=4):
                                                                    with vuetify.VCardText(class_="pa-2"):
                                                                        html.Div("Standard Colors", classes="text-caption seurat-plot-settings-popup-title")
                                                                        with html.Div(classes="seurat-plot-settings-standard-colors"):
                                                                            with vuetify.Template(
                                                                                v_for="color in plotSettingsStandardColors",
                                                                                key="row.key + ':' + color",
                                                                            ):
                                                                                html.Button(
                                                                                    "",
                                                                                    classes="seurat-plot-settings-color-swatch",
                                                                                    raw_attrs=[
                                                                                        'type="button"',
                                                                                        ':title="color"',
                                                                                        ':style="{ backgroundColor: color, boxShadow: ((row.color || \'\').toLowerCase() === color.toLowerCase()) ? \'0 0 0 2px #111\' : \'none\' }"',
                                                                                    ],
                                                                                    click=(ctrl.update_plot_series_color, "[row.key, color]"),
                                                                                )
                                                                        html.Div("More colors...", classes="text-caption seurat-plot-settings-more-colors")
                                                                        vuetify.VColorPicker(
                                                                            hide_header=True,
                                                                            hide_inputs=False,
                                                                            show_swatches=False,
                                                                            width=220,
                                                                            raw_attrs=[
                                                                                ':model-value="row.color"',
                                                                                ':modes="[\'hex\', \'rgb\', \'hsl\']"',
                                                                            ],
                                                                            update_modelValue=(ctrl.update_plot_series_color, "[row.key, $event]"),
                                                                        )
                                                        html.Div(
                                                            "{{ row.label }}",
                                                            class_="text-caption seurat-plot-settings-series-label",
                                                        )
                                                        with html.Select(
                                                            classes="seurat-plot-settings-line-style",
                                                            raw_attrs=[':value="row.line_style || \'solid\'"'],
                                                            change=(ctrl.update_plot_series_line_style, "[row.key, $event.target.value]"),
                                                        ):
                                                            html.Option("Solid", value="solid")
                                                            html.Option("Dash", value="dash")
                                                            html.Option("Dot", value="dot")
                                                            html.Option("Dash-dot", value="dash-dot")

                                with vuetify.VCardActions():
                                    with vuetify.Template(v_if="plotSettingsCanPluginOptions"):
                                        vuetify.VBtn("Plugin options...", variant="text", click=ctrl.open_plot_settings_plugin_options)
                                    vuetify.VSpacer()
                                    vuetify.VBtn("Reset", variant="text", click=ctrl.reset_plot_settings)
                                    vuetify.VBtn("Cancel", variant="text", click=ctrl.cancel_plot_settings)
                                    vuetify.VBtn("Apply", variant="tonal", click=ctrl.apply_plot_settings)

                        with html.Div(
                            id="seurat-plugin-options-panel",
                            v_show=("showPluginOptionsModal",),
                            classes="seurat-floating-options-panel",
                        ):
                            with vuetify.VCard(classes="seurat-floating-options-card", elevation=6):
                                with vuetify.VCardTitle(classes="seurat-floating-options-titlebar"):
                                    with html.Div(style="display:flex; align-items:center; gap:8px; width:100%;"):
                                        html.Div(
                                            "{{ 'Plugin Options: ' + (pluginOptionsTitle || '') }}",
                                            classes="seurat-floating-panel-drag-handle",
                                        )
                                        vuetify.VSpacer()
                                        vuetify.VBtn("Close", variant="text", size="small", click=ctrl.cancel_plugin_options)

                                with vuetify.VCardText(classes="seurat-floating-options-content"):
                                    with vuetify.Template(v_if="pluginOptionsStatus"):
                                        html.Div("{{ pluginOptionsStatus }}", class_="text-caption mb-2", style="color:#b00020;")
                                    with vuetify.Template(v_if="!(pluginOptionsRows || []).length"):
                                        html.Div("No plugin-specific options.", class_="text-caption")
                                    with html.Div(classes="seurat-plugin-options-list"):
                                        with vuetify.Template(v_for="row in pluginOptionsRows", key="row.key"):
                                            with html.Div(classes="seurat-plugin-option-row"):
                                                html.Span("{{ row.label }}", classes="seurat-plugin-option-label")
                                                with html.Div(classes="seurat-plugin-option-control"):
                                                    with vuetify.Template(v_if="row.type === 'bool'"):
                                                        html.Input(
                                                            classes="seurat-plugin-option-checkbox",
                                                            raw_attrs=[
                                                                'type="checkbox"',
                                                                ':checked="!!row.value"',
                                                            ],
                                                            change=(ctrl.update_plugin_option_value, "[row.key, $event.target.checked]"),
                                                        )
                                                    with vuetify.Template(v_if="row.type === 'select'"):
                                                        with html.Select(
                                                            classes="seurat-scalar-plot-policy seurat-plugin-option-select",
                                                            raw_attrs=[':value="row.value"'],
                                                            change=(ctrl.update_plugin_option_value, "[row.key, $event.target.value]"),
                                                        ):
                                                            with vuetify.Template(v_for="choice in row.choices", key="choice"):
                                                                html.Option("{{ choice }}", raw_attrs=[':value="choice"'])
                                                    with vuetify.Template(v_if="row.type !== 'bool' && row.type !== 'select'"):
                                                        html.Input(
                                                            classes="seurat-plugin-option-input",
                                                            raw_attrs=[
                                                                ':type="row.type === \'number\' ? \'number\' : \'text\'"',
                                                                ':value="row.value"',
                                                            ],
                                                            change=(ctrl.update_plugin_option_value, "[row.key, $event.target.value]"),
                                                        )

                                with vuetify.VCardActions():
                                    vuetify.VSpacer()
                                    vuetify.VBtn("Reset", variant="text", click=ctrl.reset_plugin_options)
                                    vuetify.VBtn("Cancel", variant="text", click=ctrl.cancel_plugin_options)
                                    vuetify.VBtn("Apply", variant="tonal", click=ctrl.apply_plugin_options)

                        with html.Div(
                            id="seurat-scalar-field-settings-panel",
                            v_show=("showScalarFieldSettingsModal",),
                            classes="seurat-floating-options-panel",
                        ):
                            with vuetify.VCard(classes="seurat-floating-options-card", elevation=6):
                                with vuetify.VCardTitle(classes="seurat-floating-options-titlebar"):
                                    with html.Div(style="display:flex; align-items:center; gap:8px; width:100%;"):
                                        html.Div(
                                            "{{ 'Plot Options: ' + (scalarFieldSettingsTitle || '') }}",
                                            classes="seurat-floating-panel-drag-handle",
                                        )
                                        vuetify.VSpacer()
                                        vuetify.VBtn(
                                            "Close",
                                            variant="text",
                                            size="small",
                                            click=ctrl.cancel_scalar_field_settings,
                                        )

                                with vuetify.VCardText(classes="seurat-floating-options-content"):
                                    with vuetify.Template(v_if="scalarFieldSettingsStatus"):
                                        html.Div(
                                            "{{ scalarFieldSettingsStatus }}",
                                            class_="text-caption mb-2",
                                            raw_attrs=[
                                                ':style="{ color: scalarFieldSettingsStatusIsError ? \'#b00020\' : \'#1b5e20\' }"'
                                            ],
                                        )

                                    html.Div("Color", classes="seurat-plot-settings-section-title")
                                    with html.Div(classes="seurat-plot-settings-section"):
                                        with html.Div(classes="seurat-plot-settings-row"):
                                            html.Span("Colormap", class_="text-caption")
                                            with html.Select(
                                                v_model=("scalarFieldSettingsColormap",),
                                                classes="seurat-scalar-plot-policy seurat-scalar-field-colormap",
                                            ):
                                                for label, value in SCALAR_FIELD_COLORMAP_OPTIONS:
                                                    html.Option(label, value=value)

                                    html.Div("Range", classes="seurat-plot-settings-section-title mt-3")
                                    with html.Div(classes="seurat-plot-settings-section"):
                                        with html.Div(classes="seurat-plot-settings-axis-row seurat-scalar-field-range-row"):
                                            with html.Div(classes="seurat-scalar-field-auto-control"):
                                                html.Input(
                                                    v_model=("scalarFieldSettingsRangeAuto",),
                                                    classes="seurat-scalar-field-auto-checkbox",
                                                    raw_attrs=['type="checkbox"'],
                                                )
                                                html.Span("Auto")
                                            html.Span(
                                                "Values:",
                                                classes="seurat-plot-settings-axis-label",
                                                raw_attrs=[
                                                    ':class="{ \'is-disabled\': scalarFieldSettingsRangeAuto }"'
                                                ],
                                            )
                                            vuetify.VTextField(
                                                v_model=("scalarFieldSettingsMin",),
                                                label="Min",
                                                density="compact",
                                                hide_details=True,
                                                raw_attrs=[':disabled="scalarFieldSettingsRangeAuto"'],
                                            )
                                            vuetify.VTextField(
                                                v_model=("scalarFieldSettingsMax",),
                                                label="Max",
                                                density="compact",
                                                hide_details=True,
                                                raw_attrs=[':disabled="scalarFieldSettingsRangeAuto"'],
                                            )

                                    html.Div("Display", classes="seurat-plot-settings-section-title mt-3")
                                    with html.Div(classes="seurat-plot-settings-section"):
                                        with html.Div(classes="seurat-scalar-field-display-options"):
                                            with html.Div(classes="seurat-scalar-field-auto-control"):
                                                html.Input(
                                                    v_model=("scalarFieldSettingsShowColorbar",),
                                                    classes="seurat-scalar-field-auto-checkbox",
                                                    raw_attrs=['type="checkbox"'],
                                                )
                                                html.Span("Show color map")
                                            with html.Div(classes="seurat-scalar-field-auto-control"):
                                                html.Input(
                                                    v_model=("scalarFieldSettingsShowAxes",),
                                                    classes="seurat-scalar-field-auto-checkbox",
                                                    raw_attrs=['type="checkbox"'],
                                                )
                                                html.Span("Show axes")

                                with vuetify.VCardActions():
                                    vuetify.VSpacer()
                                    vuetify.VBtn("Reset", variant="text", click=ctrl.reset_scalar_field_settings)
                                    vuetify.VBtn("Close", variant="text", click=ctrl.cancel_scalar_field_settings)
                                    vuetify.VBtn("Apply", variant="tonal", click=ctrl.apply_scalar_field_settings)

            with html.Div(
                id="seurat-context-menu",
                v_show=("contextMenuVisible",),
                raw_attrs=[
                    ':style="{ position: \'fixed\', zIndex: 9999, left: (contextMenuX || 0) + \'px\', top: (contextMenuY || 0) + \'px\' }"'
                ],
            ):
                html.Div("{{ contextMenuItemLabel || contextMenuItem || 'Menu' }}", classes="menu-label")

                with html.Div(v_if="contextMenuKind === 'item'"):
                    html.Div("Add To Grid", classes="menu-item", click=ctrl.context_menu_item_add)
                    html.Div("Select Variable", classes="menu-item", click=ctrl.context_menu_item_select)

                with html.Div(v_if="contextMenuKind === 'cell'"):
                    html.Div("Select Cell", classes="menu-item", click=ctrl.context_menu_cell_select)
                    with vuetify.Template(v_if="contextMenuCellCanResetView"):
                        html.Div("Reset View", classes="menu-item", click=ctrl.context_menu_cell_reset_view)
                    html.Div("Clear Cell", classes="menu-item danger", click=ctrl.context_menu_cell_clear)
                    with vuetify.Template(v_if="gridLayoutMode === 'spanning'"):
                        with html.Div(classes="menu-submenu"):
                            with html.Div(classes="menu-item menu-submenu-trigger"):
                                html.Span("Span")
                                html.Span("›", classes="menu-submenu-arrow")
                            with html.Div(classes="menu-submenu-panel"):
                                html.Div("Span right", classes="menu-item", click=ctrl.context_menu_cell_span_right)
                                html.Div("Span down", classes="menu-item", click=ctrl.context_menu_cell_span_down)
                                html.Div("Shrink width", classes="menu-item", click=ctrl.context_menu_cell_shrink_width)
                                html.Div("Shrink height", classes="menu-item", click=ctrl.context_menu_cell_shrink_height)
                                html.Div("Reset span", classes="menu-item", click=ctrl.context_menu_cell_reset_span)
                    with vuetify.Template(v_if="contextMenuCellHasVariable && !contextMenuCellCanPlotSettings"):
                        html.Div("Sources...", classes="menu-item", click=ctrl.context_menu_cell_sources)
                    with vuetify.Template(v_if="contextMenuCellCanAddSource"):
                        html.Div("Add Source", classes="menu-item", click=ctrl.context_menu_cell_add_source)
                    with vuetify.Template(v_if="contextMenuCellCanPlotSettings"):
                        html.Div("Plot settings...", classes="menu-item", click=ctrl.context_menu_cell_plot_settings)
                    with vuetify.Template(v_if="contextMenuCellCanScalarFieldSettings"):
                        html.Div("Plot options...", classes="menu-item", click=ctrl.context_menu_cell_scalar_field_settings)
                    with vuetify.Template(v_if="(contextMenuCellSourcePlugins || []).length"):
                        html.Div("Run Plugin", classes="menu-section")
                        with vuetify.Template(v_for="plugin in contextMenuCellSourcePlugins", key="plugin.plugin_id"):
                            html.Div(
                                "{{ plugin.label }}",
                                classes="menu-item",
                                click=(ctrl.context_menu_cell_run_source_plugin, "[plugin.plugin_id]"),
                            )
                    with vuetify.Template(v_if="(contextMenuCellVisualizationOptions || []).length"):
                        html.Div("Visualization Type", classes="menu-section")
                        with vuetify.Template(v_for="vis in contextMenuCellVisualizationOptions", key="vis"):
                            html.Div(
                                "{{ ((vis === contextMenuCellSelectedVisualization) ? '✓ ' : '') + vis }}",
                                classes="menu-item",
                                click=(ctrl.context_menu_cell_pick_visualization, "[vis]"),
                            )

    return layout
