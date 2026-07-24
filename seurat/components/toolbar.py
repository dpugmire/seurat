"""Query toolbar component."""

from trame.app import TrameComponent
from trame.widgets import html
from trame.widgets import vuetify3 as vuetify


class QueryToolbar(TrameComponent):
    def build(self):
        ctrl = self.ctrl
        with html.Div(classes="seurat-query-toolbar"):
            with html.Div(classes="seurat-query-command"):
                html.Span("Query", classes="seurat-query-command-label")
                vuetify.VTextField(
                    v_model=("queryText",),
                    placeholder="Filter campaign data…",
                    density="compact",
                    hide_details=True,
                    variant="solo",
                    prepend_inner_icon="mdi-filter-variant",
                    clearable=True,
                    classes="seurat-query-field",
                    keydown_enter=ctrl.run_query,
                )
            vuetify.VBtn(
                icon="mdi-help-circle-outline",
                click=ctrl.show_query_help,
                variant="text",
                size="small",
                title="Query syntax help",
                classes="seurat-query-help",
            )
            vuetify.VBtn(
                "Run query",
                prepend_icon="mdi-lightning-bolt",
                click=ctrl.run_query,
                variant="flat",
                color="primary",
                size="small",
                classes="seurat-run-query",
            )
            vuetify.VBtn(
                "Clear",
                click=ctrl.clear_query,
                variant="text",
                size="small",
                classes="seurat-clear-query",
            )
            with vuetify.Template(v_if="queryError"):
                html.Span(
                    "{{ queryError }}",
                    classes="seurat-query-error",
                    title=("queryError",),
                )
