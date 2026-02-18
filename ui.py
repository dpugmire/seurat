from trame.ui.vuetify3 import SinglePageLayout
from trame.widgets import html
from trame.widgets import vuetify3 as vuetify


def build_ui(server, refresh_variable_list, campaign_name: str = ""):
    state, ctrl = server.state, server.controller

    with SinglePageLayout(server) as layout:
        layout.title.set_text(
            f"Campaign loaded: {campaign_name}" if campaign_name else "Campaign loaded"
        )

        with layout.toolbar:
            html.Span("Query:", class_="text-caption ml-4")
            vuetify.VTextField(
                v_model=("queryText",),
                placeholder="e.g. var == 'omega' and producer == 'ns' and min > 1.0",
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
            with vuetify.VContainer(fluid=True, class_="pa-2"):
                with vuetify.VRow():
                    with vuetify.VCol(cols=2, style="display:flex; flex-direction:column; height:80vh;"):
                        with vuetify.VCard(variant="outlined", style="flex:1 1 auto; min-height:0;"):
                            with vuetify.VCardTitle():
                                html.Div("Variables")
                            with vuetify.VCardText(style="height:100%; overflow-y:auto;"):
                                with vuetify.VList(density="compact"):
                                    with vuetify.Template(v_for="v in variableNames", key="v"):
                                        vuetify.VListItem(
                                            title=("v",),
                                            active=("v === selectedVar",),
                                            click=(ctrl.pick_var, "[v]"),
                                        )

                    with vuetify.VCol(cols=10, style="display:flex; flex-direction:column; height:80vh;"):
                        with vuetify.VCard(variant="outlined", style="flex:1 1 auto; min-height:0;"):
                            with vuetify.VCardText(style="height:100%; overflow-y:auto;"):
                                with vuetify.Template(v_if="movieTiles.length"):
                                    with vuetify.VRow(dense=True):
                                        with vuetify.Template(v_for="(tile, i) in movieTiles", key="(tile._source_key || '') + '-' + (tile.selected_visualization || '') + '-' + i"):
                                            with vuetify.VCol(cols="12", sm="6", md="4", class_="pa-1"):
                                                with vuetify.VCardTitle(class_="pa-1"):
                                                    with html.Div(style="display:flex; align-items:center; gap:8px; width:100%;"):
                                                        html.Div(
                                                            "{{ selectedVar || 'variable' }}",
                                                            style="flex:1; min-width:0; font-size:0.95rem; font-weight:400; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;",
                                                        )
                                                        with vuetify.Template(v_if="tile.visualization_options && tile.visualization_options.length"):
                                                            vuetify.VSelect(
                                                                model_value=("tile.selected_visualization",),
                                                                items=("tile.visualization_options", []),
                                                                density="compact",
                                                                hide_details=True,
                                                                variant="outlined",
                                                                style="max-width:160px; font-size:0.85rem;",
                                                                change=(
                                                                    ctrl.pick_tile_visualization,
                                                                    "[(tile._source_key || ''), $event]",
                                                                ),
                                                                update_modelValue=(
                                                                    ctrl.pick_tile_visualization,
                                                                    "[(tile._source_key || ''), $event]",
                                                                ),
                                                            )
                                                        vuetify.VBtn(
                                                            "DETAILS",
                                                            size="x-small",
                                                            variant="tonal",
                                                            class_="ml-1",
                                                            click=(
                                                                ctrl.toggle_movie_details,
                                                                "[ (tile.visualization_name || '') + '|' + (tile.producer || '') + '|' + (tile.casename || '') + '|' + (tile.file || '') ]",
                                                            ),
                                                        )

                                                with vuetify.VCardText(class_="pt-0 pb-1"):
                                                    with vuetify.Template(v_if="tile.src"):
                                                        with vuetify.Template(v_if="tile.media_type === 'image'"):
                                                            html.Img(
                                                                src=("tile.src",),
                                                                style=(
                                                                    "display:block;"
                                                                    "width:100%;"
                                                                    "height:160px;"
                                                                    "object-fit:cover;"
                                                                    "border-radius:4px;"
                                                                    "background:transparent;"
                                                                ),
                                                            )
                                                        with vuetify.Template(v_else=True):
                                                            html.Video(
                                                                src=("tile.src",),
                                                                controls=True,
                                                                autoplay=False,
                                                                loop=True,
                                                                muted=True,
                                                                style=(
                                                                    "display:block;"
                                                                    "width:100%;"
                                                                    "height:160px;"
                                                                    "object-fit:cover;"
                                                                    "border-radius:4px;"
                                                                    "background:transparent;"
                                                                ),
                                                            )
                                                    with vuetify.Template(v_else=True):
                                                        html.Div(
                                                            "{{ tile.note ? tile.note : 'No movie src' }}",
                                                            class_="text-caption",
                                                            style="color:#b00020;",
                                                        )

                                                with vuetify.VExpandTransition():
                                                    with vuetify.VCardText(
                                                        class_="pt-0",
                                                        v_show=(
                                                            "movieDetailsOpen[(tile.visualization_name || '') + '|' + (tile.producer || '') + '|' + (tile.casename || '') + '|' + (tile.file || '')]"
                                                        ),
                                                    ):
                                                        with vuetify.VTable(density="compact"):
                                                            with html.Tbody():
                                                                for key in ("producer", "casename", "file"):
                                                                    with html.Tr():
                                                                        html.Td(key, class_="text-caption font-weight-medium", style="width:160px;")
                                                                        html.Td(f"{{{{ tile.{key} }}}}", class_="text-caption")
                                with vuetify.Template(v_else=True):
                                    html.Div("Select a variable to begin.", class_="text-caption", v_if="!selectedVar")
                                    html.Div("No movies for selected sources.", class_="text-caption", v_else=True)

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
                                        with vuetify.Template(v_if="selectedSourceKeys.length !== sourceRows.length"):
                                            vuetify.VBtn(
                                                "Show all",
                                                variant="text",
                                                size="small",
                                                click=ctrl.clear_source_filter,
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
                                with vuetify.Template(v_else=True):
                                    html.Div("Select a variable", class_="text-caption")

                        with vuetify.VDialog(v_model=("showSourcesModal",), max_width="1200"):
                            with vuetify.VCard():
                                with vuetify.VCardTitle():
                                    with html.Div(style="display:flex; align-items:center; gap:8px; width:100%;"):
                                        html.Div("{{ detailsSelectedVar ? ('Sources: ' + detailsSelectedVar) : 'Sources' }}")
                                        vuetify.VSpacer()
                                        with vuetify.Template(v_if="selectedSourceKeys.length !== sourceRows.length"):
                                            vuetify.VBtn(
                                                "Show all",
                                                variant="text",
                                                size="small",
                                                click=ctrl.clear_source_filter,
                                            )
                                        vuetify.VBtn("Close", variant="text", size="small", click=ctrl.toggle_sources)

                                with vuetify.VCardText():
                                    with vuetify.Template(v_if="detailsSelectedVar"):
                                        html.Div("{{ 'Visible sources: ' + selectedSourceLabel }}", class_="text-caption mb-2")
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
                                                            html.Span("Show")
                                                            with vuetify.Template(v_if="sourceSortField === 'show'"):
                                                                vuetify.VIcon(
                                                                    ("sourceSortAsc ? 'mdi-arrow-up' : 'mdi-arrow-down'",),
                                                                    size="x-small",
                                                                    class_="ml-1",
                                                                )
                                                            with vuetify.Template(v_else=True):
                                                                vuetify.VIcon("mdi-sort", size="x-small", class_="ml-1")
                                                        with html.Th(
                                                            style="cursor:pointer; user-select:none; white-space:nowrap;",
                                                            click=(ctrl.sort_sources, "['producer']"),
                                                        ):
                                                            html.Span("producer")
                                                            with vuetify.Template(v_if="sourceSortField === 'producer'"):
                                                                vuetify.VIcon(
                                                                    ("sourceSortAsc ? 'mdi-arrow-up' : 'mdi-arrow-down'",),
                                                                    size="x-small",
                                                                    class_="ml-1",
                                                                )
                                                            with vuetify.Template(v_else=True):
                                                                vuetify.VIcon("mdi-sort", size="x-small", class_="ml-1")

                                                        with html.Th(
                                                            style="cursor:pointer; user-select:none; white-space:nowrap;",
                                                            click=(ctrl.sort_sources, "['casename']"),
                                                        ):
                                                            html.Span("casename")
                                                            with vuetify.Template(v_if="sourceSortField === 'casename'"):
                                                                vuetify.VIcon(
                                                                    ("sourceSortAsc ? 'mdi-arrow-up' : 'mdi-arrow-down'",),
                                                                    size="x-small",
                                                                    class_="ml-1",
                                                                )
                                                            with vuetify.Template(v_else=True):
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
                                                            with vuetify.Template(v_else=True):
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
                                                            with vuetify.Template(v_else=True):
                                                                vuetify.VIcon("mdi-sort", size="x-small", class_="ml-1")
                                                with html.Tbody():
                                                    with vuetify.Template(v_for="(r, i) in sourceRows", key="i"):
                                                        with html.Tr(
                                                            style=(
                                                                "selectedSourceKeys.includes(r._key) ? "
                                                                "'background-color:#f5f5f5; cursor:pointer;' : "
                                                                "'cursor:pointer;'",
                                                            ),
                                                        ):
                                                            with html.Td(style="text-align:center; white-space:nowrap;"):
                                                                html.Input(
                                                                    type="checkbox",
                                                                    checked=("selectedSourceKeys.includes(r._key)",),
                                                                    click=(ctrl.toggle_source_visibility, "[r._key]"),
                                                                )
                                                            html.Td("{{ r.producer }}", style="white-space:nowrap;")
                                                            html.Td("{{ r.casename }}", style="white-space:nowrap;")
                                                            html.Td("{{ r.min }}", style="white-space:nowrap;")
                                                            html.Td("{{ r.max }}", style="white-space:nowrap;")
                                    with vuetify.Template(v_else=True):
                                        html.Div("Select a variable first.", class_="text-caption")

    return layout
