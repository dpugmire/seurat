from trame.ui.vuetify3 import SinglePageLayout
from trame.widgets import html
from trame.widgets import vuetify3 as vuetify

from config import SOURCE_FIELDS


def build_ui(server, refresh_variable_list):
    state, ctrl = server.state, server.controller

    with SinglePageLayout(server) as layout:
        layout.title.set_text("Catnip Campaign DB Viewer (Vue3)")

        with layout.toolbar:
            vuetify.VBtn(
                "Refresh variables",
                click=refresh_variable_list,
                variant="outlined",
                size="small",
            )
            vuetify.VSpacer()
            html.Div("{{ dbStatus }}", class_="text-caption")

        with layout.content:
            with vuetify.VContainer(fluid=True, class_="pa-2"):
                with vuetify.VCard(variant="outlined", class_="mb-2"):
                    with vuetify.VCardText(class_="py-2"):
                        with html.Div(style="display:flex; align-items:center; gap:10px; width:100%;"):
                            html.Span("Query:", class_="text-body-2")
                            vuetify.VTextField(
                                v_model=("queryText",),
                                placeholder="e.g. var == 'omega' and producer == 'ns' and min > 1.0",
                                density="compact",
                                hide_details=True,
                                style="max-width: 560px;",
                            )
                            vuetify.VBtn("Query", click=ctrl.run_query, variant="outlined", size="small")
                            vuetify.VBtn("Clear Query", click=ctrl.clear_query, variant="text", size="small")
                            vuetify.VSpacer()
                            html.Span("{{ queryStatus }}", class_="text-caption")

                    with vuetify.Template(v_if="queryError"):
                        with vuetify.VCardText(class_="pt-0"):
                            html.Div("{{ queryError }}", class_="text-caption", style="color:#b00020;")

                vuetify.VAlert(
                    "{{ dbStatus }}",
                    type=("dbOk ? 'success' : 'error'",),
                    variant="outlined",
                    density="compact",
                    class_="mb-2",
                )

                with vuetify.VRow():
                    with vuetify.VCol(cols=3):
                        with vuetify.VCard(variant="outlined"):
                            with vuetify.VCardTitle():
                                html.Div("Variables")
                                vuetify.VSpacer()
                                html.Div("{{ 'View: ' + queryViewLabel }}", class_="text-caption")
                            with vuetify.VCardText(style="height:80vh; overflow-y:auto;"):
                                with vuetify.VList(density="compact"):
                                    with vuetify.Template(v_for="v in variableNames", key="v"):
                                        vuetify.VListItem(
                                            title=("v",),
                                            active=("v === selectedVar",),
                                            click=(ctrl.pick_var, "[v]"),
                                        )

                    with vuetify.VCol(cols=9):
                        with vuetify.VCard(variant="outlined"):
                            with vuetify.VCardTitle():
                                with html.Div(style="display:flex; align-items:center; gap:12px; width:100%;"):
                                    html.Div("{{ detailsSelectedVar ? ('Details: ' + detailsSelectedVar) : 'Details' }}")

                                    with vuetify.Template(v_if="detailsSelectedVar"):
                                        vuetify.VBtn(
                                            "{{ 'SOURCES(' + detailsNumSources + ')' }}",
                                            variant="text",
                                            size="small",
                                            click=ctrl.toggle_sources,
                                        )
                                        vuetify.VIcon(
                                            ("showSources ? 'mdi-chevron-up' : 'mdi-chevron-down'",),
                                            size="small",
                                        )

                                    vuetify.VSpacer()
                                    html.Div("{{ 'QueryView: ' + queryViewLabel }}", class_="text-caption")

                            with vuetify.VCardText(style="height:36vh; overflow-y:auto;"):
                                with vuetify.Template(v_if="detailsSelectedVar"):
                                    with vuetify.VRow(dense=True):
                                        with vuetify.VCol(cols=5):
                                            with vuetify.VTable(density="compact"):
                                                with html.Thead():
                                                    with html.Tr():
                                                        html.Th("")
                                                        html.Th("Min")
                                                        html.Th("Max")
                                                with html.Tbody():
                                                    with html.Tr():
                                                        html.Td("Global")
                                                        html.Td("{{ detailsGlobalMin }}")
                                                        html.Td("{{ detailsGlobalMax }}")
                                                    with html.Tr():
                                                        html.Td("Median")
                                                        html.Td("{{ detailsMedianMin }}")
                                                        html.Td("{{ detailsMedianMax }}")
                                                    with html.Tr():
                                                        html.Td("Mean")
                                                        html.Td("{{ detailsMeanMin }}")
                                                        html.Td("{{ detailsMeanMax }}")

                                        with vuetify.VCol(cols=7):
                                            with vuetify.Template(v_if="showSources"):
                                                with html.Div(
                                                    style=(
                                                        "max-height:30vh;"
                                                        "overflow-y:auto;"
                                                        "overflow-x:scroll;"
                                                        "white-space:nowrap;"
                                                        "scrollbar-gutter:stable;"
                                                    )
                                                ):
                                                    with vuetify.VTable(density="compact"):
                                                        with html.Thead():
                                                            with html.Tr():
                                                                for f in SOURCE_FIELDS:
                                                                    with html.Th(
                                                                        style="cursor:pointer; user-select:none; white-space:nowrap;",
                                                                        click=(ctrl.sort_sources, f"['{f}']"),
                                                                    ):
                                                                        html.Span(f)
                                                                        with vuetify.Template(v_if=(f"sourceSortField === '{f}'",)):
                                                                            vuetify.VIcon(
                                                                                ("sourceSortAsc ? 'mdi-arrow-up' : 'mdi-arrow-down'",),
                                                                                size="x-small",
                                                                                class_="ml-1",
                                                                            )
                                                                        with vuetify.Template(v_else=True):
                                                                            vuetify.VIcon("mdi-sort", size="x-small", class_="ml-1")
                                                        with html.Tbody():
                                                            with vuetify.Template(v_for="(r, i) in sourceRows", key="i"):
                                                                with html.Tr():
                                                                    html.Td("{{ r.producer }}", style="white-space:nowrap;")
                                                                    html.Td("{{ r.casename }}", style="white-space:nowrap;")
                                                                    html.Td("{{ r.file }}", style="white-space:nowrap;")
                                                                    html.Td("{{ r.min }}", style="white-space:nowrap;")
                                                                    html.Td("{{ r.max }}", style="white-space:nowrap;")
                                            with vuetify.Template(v_else=True):
                                                html.Div("Sources table.", class_="text-caption")
                                with vuetify.Template(v_else=True):
                                    html.Div("Select a variable", class_="text-caption")

                        html.Div(style="height: 8px")

                        with vuetify.VCard(variant="outlined"):
                            with vuetify.VCardTitle():
                                html.Div("Visualizations")
                                vuetify.VSpacer()
                                html.Div("{{ movieStatus }}", class_="text-caption")
                            with vuetify.VCardText(style="height:42vh; overflow-y:auto;"):
                                with vuetify.Template(v_if="movieTiles.length"):
                                    with vuetify.VRow(dense=True):
                                        with vuetify.Template(v_for="(tile, i) in movieTiles", key="i"):
                                            with vuetify.VCol(cols="12", sm="6", md="4", class_="pa-1"):
                                                with vuetify.VCardTitle(class_="pa-1"):
                                                    with html.Div(style="display:flex; align-items:center; gap:8px; width:100%;"):
                                                        html.Div(
                                                            "{{ tile.visualization_name || 'visualization' }}",
                                                            style="flex:1; min-width:0; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;",
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
                                                        html.Video(
                                                            src=("tile.src",),
                                                            controls=True,
                                                            autoplay=False,
                                                            loop=True,
                                                            muted=True,
                                                            style=(
                                                                "display:block;"
                                                                "width:100%;"
                                                                "height:240px;"
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
                                                                for key in ("producer", "casename", "file", "status", "note"):
                                                                    with html.Tr():
                                                                        html.Td(key, class_="text-caption font-weight-medium", style="width:160px;")
                                                                        html.Td(("tile." + key, ), class_="text-caption")
                                with vuetify.Template(v_else=True):
                                    html.Div("Select a variable to begin.", class_="text-caption", v_if="!selectedVar")
                                    html.Div("No movies in this QueryView.", class_="text-caption", v_else=True)

    return layout
