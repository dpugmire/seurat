"""Explainable, explicitly actionable preference suggestions."""

from trame.app import TrameComponent
from trame.widgets import html
from trame.widgets import vuetify3 as vuetify


class PreferenceSuggestionDialog(TrameComponent):
    def build(self):
        ctrl = self.ctrl
        with vuetify.VDialog(
            v_model=("showPreferenceSuggestion",),
            max_width="620",
            persistent=True,
        ):
            with vuetify.VCard():
                vuetify.VCardTitle(
                    "{{ preferenceSuggestionTitle || 'Suggestion' }}"
                )
                with vuetify.VCardText():
                    html.Div(
                        "{{ preferenceSuggestionMessage }}",
                        class_="text-body-2 mb-3",
                    )
                    with vuetify.Template(
                        v_if="preferenceSuggestionType === 'visualization'"
                    ):
                        html.Div(
                            "{{ 'Variable: ' + preferenceSuggestionVariableId }}",
                            class_="text-body-2",
                        )
                        html.Div(
                            "{{ 'Current: ' + preferenceSuggestionCurrentVisualization }}",
                            class_="text-body-2 mt-1",
                        )
                        html.Div(
                            "{{ 'Suggested: ' + preferenceSuggestionRecommendedVisualization }}",
                            class_="text-body-2 font-weight-bold mt-1",
                        )
                    with vuetify.Template(
                        v_if="preferenceSuggestionType === 'workspace'"
                    ):
                        html.Div(
                            "Suggested tab variables",
                            class_="text-caption font-weight-bold mb-2",
                        )
                        with html.Div(
                            style="display:flex; flex-wrap:wrap; gap:6px;"
                        ):
                            with vuetify.Template(
                                v_for="variable in preferenceSuggestionVariables",
                                key="variable",
                            ):
                                vuetify.VChip(
                                    "{{ variable }}",
                                    size="small",
                                    variant="tonal",
                                )
                    html.Div(
                        "{{ 'Confidence: ' + Math.round(100 * "
                        "Number(preferenceSuggestionConfidence || 0)) + "
                        "'% · Evidence: ' + "
                        "Number(preferenceSuggestionEvidenceCount || 0) + "
                        "' signals across ' + "
                        "Number(preferenceSuggestionSessionCount || 0) + "
                        "' sessions' }}",
                        class_="text-caption text-medium-emphasis mt-3",
                    )
                    with vuetify.Template(v_if="preferenceSuggestionStatus"):
                        html.Div(
                            "{{ preferenceSuggestionStatus }}",
                            class_="text-caption mt-3",
                            style="color:#b00020;",
                        )
                with vuetify.VCardActions():
                    vuetify.VSpacer()
                    vuetify.VBtn(
                        "Dismiss",
                        variant="text",
                        click=ctrl.dismiss_preference_suggestion,
                    )
                    with vuetify.Template(
                        v_if="preferenceSuggestionType === 'visualization'"
                    ):
                        vuetify.VBtn(
                            "Choose Another",
                            variant="text",
                            click=ctrl.choose_preference_alternative,
                        )
                    vuetify.VBtn(
                        "{{ preferenceSuggestionType === 'workspace' "
                        "? 'Create Tab' : 'Use Suggestion' }}",
                        color="primary",
                        variant="tonal",
                        click=ctrl.accept_preference_suggestion,
                    )
