"""Query toolbar component."""

from trame.app import TrameComponent
from trame.widgets import html
from trame.widgets import vuetify3 as vuetify


class QueryToolbar(TrameComponent):
    def build(self):
        ctrl = self.ctrl
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
        vuetify.VBtn(
            "Clear",
            click=ctrl.clear_query,
            variant="text",
            size="small",
            class_="ml-1",
        )
        with vuetify.Template(v_if="queryError"):
            html.Span(
                "{{ queryError }}",
                class_="text-caption ml-2",
                style="color:#b00020;",
            )
