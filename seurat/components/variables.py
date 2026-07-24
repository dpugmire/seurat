"""Variable catalog component."""

from trame.app import TrameComponent
from trame.widgets import html
from trame.widgets import vuetify3 as vuetify


class VariablePanel(TrameComponent):
    def build(self):
        ctrl = self.ctrl
        group_kind = (
            "(((group.name || '').toLowerCase().includes('image')"
            " || (group.name || '').toLowerCase().includes('movie')"
            " || (group.name || '').toLowerCase().includes('img'))"
            " ? 'img'"
            " : ((group.name || '').toLowerCase().includes('0d') ? '0d'"
            " : ((group.name || '').toLowerCase().includes('1d') ? '1d'"
            " : ((group.name || '').toLowerCase().includes('2d') ? '2d'"
            " : ((group.name || '').toLowerCase().includes('3d') ? '3d' : 'other')))))"
        )
        matches_group_type = (
            f"(variableTypeFilter === 'all' || {group_kind} === variableTypeFilter)"
        )
        matches_search = (
            "(!(variableSearchText || '').trim()"
            " || (group.variables || []).some(v =>"
            " [v.label, v.name, v.id, v.path].join(' ').toLowerCase()"
            ".includes((variableSearchText || '').trim().toLowerCase())))"
        )
        with vuetify.VCol(
            id="seurat-variable-column",
            classes="seurat-variable-column",
            style="display:flex; flex-direction:column;",
        ):
            with vuetify.VCard(
                variant="flat",
                classes="seurat-variable-card",
            ):
                with vuetify.VCardTitle(classes="seurat-sidebar-title"):
                    with html.Div(classes="seurat-sidebar-heading"):
                        html.Div("Data catalog", classes="seurat-sidebar-eyebrow")
                        with html.Div(classes="seurat-sidebar-title-row"):
                            html.Div("Variables")
                            html.Div(
                                "{{ (variableNames || []).length }}",
                                classes="seurat-variable-total",
                            )
                with vuetify.VCardText(classes="seurat-variable-card-content"):
                    vuetify.VTextField(
                        v_model=("variableSearchText",),
                        placeholder="Search variables",
                        prepend_inner_icon="mdi-magnify",
                        density="compact",
                        variant="outlined",
                        hide_details=True,
                        clearable=True,
                        classes="seurat-variable-search",
                    )
                    with vuetify.VBtnToggle(
                        v_model=("variableTypeFilter",),
                        mandatory=True,
                        density="compact",
                        variant="outlined",
                        classes="seurat-variable-type-filter",
                    ):
                        vuetify.VBtn("All", value="all", size="small")
                        vuetify.VBtn("0D", value="0d", size="small")
                        vuetify.VBtn("1D", value="1d", size="small")
                        vuetify.VBtn("2D", value="2d", size="small")
                        vuetify.VBtn("Img", value="img", size="small")
                    with html.Div(classes="seurat-variable-options"):
                        html.Span("Group by", classes="seurat-variable-options-label")
                        with vuetify.VBtnToggle(
                            v_model=("variablePaneView",),
                            mandatory=True,
                            density="compact",
                            variant="text",
                            classes="seurat-group-by-toggle",
                        ):
                            vuetify.VBtn("Variable", value="variables", size="small")
                            vuetify.VBtn("File", value="files", size="small")
                        vuetify.VCheckbox(
                            v_model=("showOnlyVisualizedVars",),
                            label="Visualized",
                            density="compact",
                            hide_details=True,
                            classes="seurat-visualized-filter",
                        )
                    with vuetify.VList(
                        density="compact",
                        classes="seurat-var-list",
                    ):
                        html.Div(
                            "No variables",
                            v_if="!(variableGroups || []).length",
                            classes="seurat-variable-empty",
                        )
                        html.Div(
                            "No matching variables",
                            v_if=(
                                "(variableGroups || []).length"
                                " && !(variableGroups || []).some(group =>"
                                f" {matches_group_type}"
                                f" && {matches_search})"
                            ),
                            classes="seurat-variable-empty",
                        )
                        with vuetify.Template(v_for="group in variableGroups", key="group.name"):
                            with html.Div(
                                classes="seurat-var-group",
                                v_show=(
                                    f"{matches_group_type} && {matches_search}"
                                ),
                                raw_attrs=[f':data-kind="{group_kind}"'],
                            ):
                                with html.Button(
                                    click=(ctrl.toggle_variable_group, "[group.name]"),
                                    style="font-weight:800;",
                                    raw_attrs=[
                                        'type="button"',
                                        'class="seurat-var-group-title"',
                                        ':aria-expanded="!(variableGroupCollapsed && variableGroupCollapsed[group.name])"',
                                    ],
                                ):
                                    html.Span(
                                        "{{ (variableGroupCollapsed && variableGroupCollapsed[group.name]) ? '▸' : '▾' }}",
                                        raw_attrs=['class="seurat-var-group-chevron"'],
                                    )
                                    html.Span(
                                        "",
                                        classes="seurat-variable-kind-dot",
                                        raw_attrs=['aria-hidden="true"'],
                                    )
                                    html.Span(
                                        "{{ group.name }}",
                                        raw_attrs=[':title="group.name"'],
                                        classes="seurat-var-group-name",
                                    )
                                    html.Span(
                                        "{{ (group.variables || []).length }}",
                                        classes="seurat-var-group-count",
                                    )
                                with html.Div(v_if="!(variableGroupCollapsed && variableGroupCollapsed[group.name])"):
                                    with vuetify.Template(v_for="v in group.variables", key="group.name + '::' + v.id"):
                                        with html.Div(
                                            v_show=(
                                                "!(variableSearchText || '').trim()"
                                                " || [v.label, v.name, v.id, v.path].join(' ').toLowerCase().includes((variableSearchText || '').trim().toLowerCase())"
                                            ),
                                            click=(ctrl.pick_var, "[v.id]"),
                                            draggable="true",
                                            classes="seurat-draggable-var seurat-var-item",
                                            raw_attrs=[':data-item="v.id"', ':title="v.path || v.id"'],
                                            style="((v.id === selectedVar) ? 'background:var(--seurat-selection-soft);' : '')",
                                        ):
                                            html.Span(
                                                "",
                                                classes="seurat-variable-item-dot",
                                                raw_attrs=['aria-hidden="true"'],
                                            )
                                            html.Span(
                                                "{{ v.label || v.name || v.id }}",
                                                classes="seurat-variable-item-label",
                                            )
                    with html.Div(classes="seurat-variable-footer"):
                        vuetify.VIcon("mdi-drag-variant", size=16)
                        html.Span("Drag a variable onto the workspace")

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
