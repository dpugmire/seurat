from trame.ui.vuetify3 import SinglePageLayout
from trame.widgets import client, html
from trame.widgets import vuetify3 as vuetify


def build_ui(server, refresh_variable_list, campaign_name: str = ""):
    state, ctrl = server.state, server.controller
    drag_drop_js = """
    (function initCatnipDragDrop() {
      try {
        if (window.__catnipDnDInit) return;
        if (typeof window.trame === "undefined") {
          setTimeout(initCatnipDragDrop, 200);
          return;
        }
        window.__catnipDnDInit = true;

        document.addEventListener("dragstart", function(e) {
          const target = e && e.target;
          if (!target || !target.closest) return;
          if (!e.dataTransfer) return;

          const varEl = target.closest(".catnip-draggable-var");
          if (varEl) {
            const item = varEl.getAttribute("data-item") || "";
            if (!item) return;
            e.dataTransfer.setData("text/plain", item);
            e.dataTransfer.setData("application/x-catnip-var", item);
            e.dataTransfer.effectAllowed = "copy";
            varEl.style.opacity = "0.45";
            return;
          }

          const cellEl = target.closest(".catnip-dropcell");
          if (!cellEl) return;
          const filled = cellEl.getAttribute("data-cell-filled");
          const fromIdx = cellEl.getAttribute("data-cell-index");
          if (filled !== "1" || fromIdx === null) return;
          e.dataTransfer.setData("application/x-catnip-grid-cell", fromIdx);
          e.dataTransfer.effectAllowed = "move";
          cellEl.style.opacity = "0.55";
        });

        document.addEventListener("dragend", function(e) {
          const target = e && e.target;
          if (!target || !target.closest) return;
          const varEl = target.closest(".catnip-draggable-var");
          if (varEl) varEl.style.opacity = "1";
          const cellEl = target.closest(".catnip-dropcell");
          if (cellEl) cellEl.style.opacity = "1";
        });

        document.addEventListener("dragover", function(e) {
          const target = e && e.target;
          if (!target || !target.closest) return;
          const el = target.closest(".catnip-dropcell");
          if (!el) return;
          e.preventDefault();
          if (e.dataTransfer) {
            const types = Array.from(e.dataTransfer.types || []);
            e.dataTransfer.dropEffect = types.includes("application/x-catnip-grid-cell") ? "move" : "copy";
          }
          el.classList.add("catnip-drop-hover");
        });

        document.addEventListener("dragleave", function(e) {
          const target = e && e.target;
          if (!target || !target.closest) return;
          const el = target.closest(".catnip-dropcell");
          if (!el) return;
          if (!el.contains(e.relatedTarget)) {
            el.classList.remove("catnip-drop-hover");
          }
        });

        document.addEventListener("drop", function(e) {
          const target = e && e.target;
          if (!target || !target.closest) return;
          const el = target.closest(".catnip-dropcell");
          if (!el) return;
          e.preventDefault();
          el.classList.remove("catnip-drop-hover");
          const fromCell = e.dataTransfer ? (e.dataTransfer.getData("application/x-catnip-grid-cell") || "") : "";
          const idx = el.getAttribute("data-cell-index");
          if (fromCell !== "" && idx !== null) {
            if (window.trame && window.trame.trigger) {
              window.trame.trigger("move_grid_cell_trigger", [fromCell, idx]);
            }
            return;
          }
          const item = e.dataTransfer
            ? (e.dataTransfer.getData("text/plain") || e.dataTransfer.getData("application/x-catnip-var") || "")
            : "";
          if (!item || idx === null) return;
          if (window.trame && window.trame.trigger) {
            window.trame.trigger("assign_var_to_grid_cell_trigger", [item, idx]);
          }
        });

        document.addEventListener("contextmenu", function(e) {
          const target = e && e.target;
          if (!target || !target.closest) return;

          if (target.closest("#catnip-context-menu")) return;

          const itemEl = target.closest(".catnip-draggable-var");
          if (itemEl) {
            e.preventDefault();
            const item = itemEl.getAttribute("data-item") || "";
            if (item && window.trame && window.trame.trigger) {
              window.trame.trigger("show_item_context_menu", [item, (e.clientX || 0), (e.clientY || 0)]);
            }
            return;
          }

          const cellEl = target.closest(".catnip-dropcell");
          if (cellEl) {
            e.preventDefault();
            const idx = cellEl.getAttribute("data-cell-index");
            if (idx !== null && window.trame && window.trame.trigger) {
              window.trame.trigger("show_cell_context_menu", [idx, (e.clientX || 0), (e.clientY || 0)]);
            }
            return;
          }

          if (window.trame && window.trame.trigger) {
            window.trame.trigger("hide_context_menu_trigger", []);
          }
        });

        document.addEventListener("click", function(e) {
          const target = e && e.target;
          if (!target || !target.closest || !target.closest("#catnip-context-menu")) {
            if (window.trame && window.trame.trigger) {
              window.trame.trigger("hide_context_menu_trigger", []);
            }
          }
        });
      } catch (err) {
        console.error("catnip drag/drop init failed", err);
      }
    })();
    """

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
            client.Script(drag_drop_js)
            client.Style(
                """
                .catnip-draggable-var { cursor: grab; user-select: none; }
                .catnip-draggable-var:active { cursor: grabbing; }
                .catnip-dropcell { transition: background 0.15s, box-shadow 0.15s; }
                .catnip-drop-hover {
                  background: #e3f2fd !important;
                  box-shadow: inset 0 0 0 2px #1976d2 !important;
                }
                #catnip-context-menu {
                  background: #fff;
                  border: 1px solid #c9c9c9;
                  border-radius: 4px;
                  box-shadow: 0 3px 12px rgba(0, 0, 0, 0.2);
                  min-width: 170px;
                  padding: 4px 0;
                }
                #catnip-context-menu .menu-item {
                  padding: 7px 12px;
                  cursor: pointer;
                  font-size: 13px;
                  line-height: 1.2;
                  user-select: none;
                }
                #catnip-context-menu .menu-item:hover {
                  background: #e3f2fd;
                }
                #catnip-context-menu .menu-item.danger:hover {
                  background: #ffebee;
                  color: #c62828;
                }
                #catnip-context-menu .menu-label {
                  padding: 6px 12px 4px;
                  font-size: 11px;
                  color: #666;
                  border-bottom: 1px solid #ececec;
                  margin-bottom: 4px;
                  white-space: nowrap;
                  overflow: hidden;
                  text-overflow: ellipsis;
                }
                """
            )
            with vuetify.VContainer(fluid=True, class_="pa-2"):
                with vuetify.VRow():
                    with vuetify.VCol(cols=2, style="display:flex; flex-direction:column; height:80vh;"):
                        with vuetify.VCard(variant="outlined", style="flex:1 1 auto; min-height:0;"):
                            with vuetify.VCardTitle():
                                html.Div("Variables")
                            with vuetify.VCardText(style="height:100%; overflow-y:auto;"):
                                with vuetify.VList(density="compact"):
                                    with vuetify.Template(v_for="v in variableNames", key="v"):
                                        with html.Div(
                                            click=(ctrl.pick_var, "[v]"),
                                            draggable="true",
                                            classes="catnip-draggable-var",
                                            raw_attrs=[':data-item="v"'],
                                            style=(
                                                "('padding:8px 10px; border-radius:4px; cursor:grab; user-select:none;'"
                                                " + ((v === selectedVar) ? 'background:#e8e8e8;' : ''))",
                                            ),
                                        ):
                                            html.Span("{{ v }}")

                    with vuetify.VCol(cols=10, style="display:flex; flex-direction:column; height:80vh;"):
                        with vuetify.VCard(variant="outlined", style="flex:1 1 auto; min-height:0;"):
                            with vuetify.VCardText(style="height:100%; overflow:auto;"):
                                with html.Div(
                                    style=(
                                        "display:grid;"
                                        "grid-template-columns:repeat(3, 300px);"
                                        "grid-template-rows:repeat(3, 332px);"
                                        "width:max-content;"
                                        "margin:0 auto;"
                                        "justify-content:center;"
                                        "align-content:start;"
                                        "border:1px solid #cfcfcf;"
                                    )
                                ):
                                    with vuetify.Template(v_for="(tile, i) in gridCells", key="i"):
                                        with html.Div(
                                            click=(
                                                ctrl.set_active_grid_cell,
                                                "[i, (($event && $event.target && $event.target.closest && $event.target.closest('.catnip-cell-close')) ? 1 : 0)]",
                                            ),
                                            classes="catnip-dropcell",
                                            raw_attrs=[
                                                ':data-cell-index="i"',
                                                ':data-cell-filled="((tile && tile.variable_name) ? 1 : 0)"',
                                                ':draggable="!!(tile && tile.variable_name)"',
                                            ],
                                            style=(
                                                "('width:300px; height:332px; overflow:hidden; cursor:pointer; display:flex; flex-direction:column;'"
                                                " + ((i % 3 !== 2) ? 'border-right:1px solid #cfcfcf;' : '')"
                                                " + ((i < 6) ? 'border-bottom:1px solid #cfcfcf;' : '')"
                                                " + ((activeGridCell === i) ? 'background:#eef5ff; box-shadow: inset 0 0 0 2px #1e88e5;' : ''))",
                                            ),
                                        ):
                                            with vuetify.Template(v_if="tile && tile.variable_name"):
                                                with html.Div(
                                                    style=(
                                                        "display:flex;"
                                                        "align-items:center;"
                                                        "gap:8px;"
                                                        "width:100%;"
                                                        "height:32px;"
                                                        "padding:4px 6px;"
                                                        "background:#7bd0ef;"
                                                        "border-bottom:1px solid #3ca7c9;"
                                                    ),
                                                ):
                                                    html.Div(
                                                        "{{ tile.variable_name || 'variable' }}",
                                                        style="flex:1; min-width:0; font-size:0.9rem; font-weight:400; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;",
                                                    )
                                                    html.Button(
                                                        "x",
                                                        classes="catnip-cell-close",
                                                        click=(ctrl.clear_grid_cell, "[i]"),
                                                        style=(
                                                            "margin-left:auto;"
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

                                                with html.Div(style="width:300px; height:300px; background:#111;"):
                                                    with vuetify.Template(v_if="tile.src"):
                                                        with vuetify.Template(v_if="tile.media_type === 'image'"):
                                                            html.Img(
                                                                src=("tile.src",),
                                                                style=(
                                                                    "display:block;"
                                                                    "width:300px;"
                                                                    "height:300px;"
                                                                    "object-fit:contain;"
                                                                    "background:#111;"
                                                                ),
                                                            )
                                                        with vuetify.Template(v_if="tile.media_type !== 'image'"):
                                                            html.Video(
                                                                src=("tile.src",),
                                                                controls=True,
                                                                autoplay=False,
                                                                loop=True,
                                                                muted=True,
                                                                style=(
                                                                    "display:block;"
                                                                    "width:300px;"
                                                                    "height:300px;"
                                                                    "object-fit:contain;"
                                                                    "background:#111;"
                                                                ),
                                                            )
                                                    with vuetify.Template(v_if="!tile.src"):
                                                        html.Div(
                                                            "{{ tile.note ? tile.note : 'No movie src' }}",
                                                            class_="text-caption",
                                                            style=(
                                                                "height:300px;"
                                                                "display:flex;"
                                                                "align-items:center;"
                                                                "justify-content:center;"
                                                                "text-align:center;"
                                                                "padding:8px;"
                                                                "color:#ddd;"
                                                            ),
                                                        )
                                            with vuetify.Template(v_if="!(tile && tile.variable_name)"):
                                                html.Div(
                                                    "Drop variable here",
                                                    class_="text-caption",
                                                    style=(
                                                        "height:100%;"
                                                        "display:flex;"
                                                        "align-items:center;"
                                                        "justify-content:center;"
                                                        "color:#777;"
                                                    ),
                                                )

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
                                        with vuetify.Template(v_if="(selectedSourceKeys || []).length !== (sourceRows || []).length"):
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
                                with vuetify.Template(v_if="!detailsSelectedVar"):
                                    html.Div("Select a variable", class_="text-caption")

                        with vuetify.VDialog(v_model=("showSourcesModal",), max_width="1200"):
                            with vuetify.VCard():
                                with vuetify.VCardTitle():
                                    with html.Div(style="display:flex; align-items:center; gap:8px; width:100%;"):
                                        html.Div("{{ detailsSelectedVar ? ('Sources: ' + detailsSelectedVar) : 'Sources' }}")
                                        vuetify.VSpacer()
                                        with vuetify.Template(v_if="(selectedSourceKeys || []).length !== (sourceRows || []).length"):
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
                                                            with vuetify.Template(v_if="sourceSortField !== 'show'"):
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
                                                            with vuetify.Template(v_if="sourceSortField !== 'producer'"):
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
                                                            with vuetify.Template(v_if="sourceSortField !== 'casename'"):
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
                                                        ):
                                                            with html.Td(style="text-align:center; white-space:nowrap;"):
                                                                html.Input(
                                                                    type="checkbox",
                                                                    checked=("((selectedSourceKeys || []).includes(r._key))",),
                                                                    click=(ctrl.toggle_source_visibility, "[r._key]"),
                                                                )
                                                            html.Td("{{ r.producer }}", style="white-space:nowrap;")
                                                            html.Td("{{ r.casename }}", style="white-space:nowrap;")
                                                            html.Td("{{ r.min }}", style="white-space:nowrap;")
                                                            html.Td("{{ r.max }}", style="white-space:nowrap;")
                                        with vuetify.Template(v_if="!detailsSelectedVar"):
                                            html.Div("Select a variable first.", class_="text-caption")

            with html.Div(
                id="catnip-context-menu",
                v_show=("contextMenuVisible",),
                raw_attrs=[
                    ':style="{ position: \'fixed\', zIndex: 9999, left: (contextMenuX || 0) + \'px\', top: (contextMenuY || 0) + \'px\' }"'
                ],
            ):
                html.Div("{{ contextMenuItem || 'Menu' }}", classes="menu-label")

                with html.Div(v_if="contextMenuKind === 'item'"):
                    html.Div("Add To Grid", classes="menu-item", click=ctrl.context_menu_item_add)
                    html.Div("Select Variable", classes="menu-item", click=ctrl.context_menu_item_select)

                with html.Div(v_if="contextMenuKind === 'cell'"):
                    html.Div("Select Cell", classes="menu-item", click=ctrl.context_menu_cell_select)
                    html.Div("Clear Cell", classes="menu-item danger", click=ctrl.context_menu_cell_clear)

    return layout
