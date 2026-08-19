import json
import stat
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

from seurat.controllers.base import ControllerBase
from seurat.controllers.context import ControllerContext
from seurat.controllers.preferences import PreferenceControllerMixin
from seurat.learning.build_profile import write_profile
from seurat.learning.builder import build_preference_profile
from seurat.learning.evaluate import evaluate_events
from seurat.learning.labels import visualization_preference_examples
from seurat.learning.profile import PreferenceProfile
from seurat.state import init_state


def event(session, sequence, event_type, payload, *, day=1):
    return {
        "schema_version": 1,
        "event_id": f"event:{session}:{sequence}",
        "event_sequence": sequence,
        "timestamp_utc": f"2026-08-{day:02d}T12:00:{sequence:02d}.000Z",
        "elapsed_session_ms": sequence * 1000,
        "user_profile_id": "profile:test",
        "session_id": session,
        "campaign_version_id": "campaign:test",
        "event_type": event_type,
        "source": "test",
        "model_version": "capture-v1",
        "payload": payload,
    }


def corrected_session(session, day, variable="pressure"):
    assignment = event(
        session,
        1,
        "visualization.assigned",
        {
            "variable_id": variable,
            "candidate_visualizations": ["heatmap", "scalar_field"],
            "selected_visualization": "heatmap",
            "selection_origin": "default",
            "variable_features": {
                "variable_type": "scalar",
                "dimensionality": 2,
                "time_varying": True,
            },
        },
        day=day,
    )
    change = event(
        session,
        2,
        "visualization.changed",
        {
            "variable_id": variable,
            "previous_visualization": "heatmap",
            "selected_visualization": "scalar_field",
            "assignment_event_id": assignment["event_id"],
        },
        day=day,
    )
    return [assignment, change]


def saved_workspace(session, day):
    return event(
        session,
        3,
        "workspace.saved",
        {
            "workspace": {
                "panes": [
                    {
                        "tabs": [
                            {
                                "grid": {
                                    "cells": [
                                        {"variable_id": "pressure"},
                                        {"variable_id": "temperature"},
                                        {"variable_id": "density"},
                                    ]
                                }
                            }
                        ]
                    }
                ]
            }
        },
        day=day,
    )


class PreferenceLearningTests(unittest.TestCase):
    def test_correction_becomes_explicit_pairwise_preference(self):
        events = corrected_session("session:1", 1)

        examples = visualization_preference_examples(events)

        self.assertEqual(len(examples), 1)
        self.assertEqual(examples[0].baseline_visualization, "heatmap")
        self.assertEqual(examples[0].preferred_visualization, "scalar_field")
        self.assertEqual(examples[0].rejected_visualizations, ("heatmap",))
        self.assertEqual(examples[0].reason, "manual_correction")

    def test_quick_removal_is_negative_but_not_a_positive_choice(self):
        assignment = corrected_session("session:1", 1)[0]
        removal = event(
            "session:1",
            2,
            "visualization.removed",
            {
                "variable_id": "pressure",
                "visualization_id": "heatmap",
                "assignment_event_id": assignment["event_id"],
                "elapsed_since_assignment_ms": 4_000,
            },
        )

        examples = visualization_preference_examples([assignment, removal])

        self.assertEqual(len(examples), 1)
        self.assertEqual(examples[0].preferred_visualization, "")
        self.assertEqual(examples[0].rejected_visualizations, ("heatmap",))
        self.assertEqual(examples[0].weight, 0.5)

    def test_profile_recommends_only_after_cross_session_evidence(self):
        events = []
        for day in range(1, 4):
            events.extend(corrected_session(f"session:{day}", day))
        profile = PreferenceProfile(build_preference_profile(events))

        recommendation = profile.recommend_visualization(
            "pressure",
            ["heatmap", "scalar_field"],
            variable_features={"variable_type": "scalar", "dimensionality": 2},
        )

        self.assertIsNotNone(recommendation)
        self.assertEqual(recommendation.visualization_id, "scalar_field")
        self.assertEqual(recommendation.scope, "variable")
        self.assertEqual(recommendation.evidence_count, 3)
        self.assertEqual(recommendation.session_count, 3)

    def test_feature_profile_generalizes_to_unseen_variable(self):
        events = []
        for day, variable in enumerate(("pressure", "temperature", "density"), 1):
            events.extend(corrected_session(f"session:{day}", day, variable))
        profile = PreferenceProfile(build_preference_profile(events))

        recommendation = profile.recommend_visualization(
            "unseen",
            ["heatmap", "scalar_field"],
            variable_features={
                "variable_type": "scalar",
                "dimensionality": 2,
                "time_varying": True,
            },
        )

        self.assertIsNotNone(recommendation)
        self.assertEqual(recommendation.visualization_id, "scalar_field")
        self.assertEqual(recommendation.scope, "features")

    def test_query_context_can_override_ambiguous_variable_preference(self):
        events = []
        for day in range(1, 4):
            forward = corrected_session(f"session:forward:{day}", day)
            forward[0]["payload"]["query_feature_key"] = "query-context:forward"
            events.extend(forward)

            reverse = corrected_session(f"session:reverse:{day}", day + 3)
            reverse[0]["payload"].update(
                {
                    "selected_visualization": "scalar_field",
                    "query_feature_key": "query-context:reverse",
                }
            )
            reverse[1]["payload"].update(
                {
                    "previous_visualization": "scalar_field",
                    "selected_visualization": "heatmap",
                }
            )
            events.extend(reverse)
        profile = PreferenceProfile(build_preference_profile(events))

        forward = profile.recommend_visualization(
            "pressure",
            ["heatmap", "scalar_field"],
            query_feature_key="query-context:forward",
        )
        reverse = profile.recommend_visualization(
            "pressure",
            ["heatmap", "scalar_field"],
            query_feature_key="query-context:reverse",
        )

        self.assertEqual(forward.visualization_id, "scalar_field")
        self.assertEqual(reverse.visualization_id, "heatmap")
        self.assertEqual(forward.scope, "query")
        self.assertEqual(reverse.scope, "query")

    def test_workspace_profile_suggests_repeated_saved_group(self):
        events = [
            saved_workspace("session:1", 1),
            saved_workspace("session:2", 2),
            saved_workspace("session:3", 3),
        ]
        profile = PreferenceProfile(build_preference_profile(events))

        recommendation = profile.recommend_workspace(
            existing_tabs=[[]],
            available_variables=["pressure", "temperature", "density"],
        )
        duplicate = profile.recommend_workspace(
            existing_tabs=[["pressure", "temperature", "density"]],
            available_variables=["pressure", "temperature", "density"],
        )

        self.assertIsNotNone(recommendation)
        self.assertEqual(
            recommendation.variables,
            ("density", "pressure", "temperature"),
        )
        self.assertIsNone(duplicate)

    def test_walk_forward_evaluation_never_trains_on_current_session(self):
        events = []
        for day in range(1, 4):
            events.extend(corrected_session(f"session:{day}", day))

        result = evaluate_events(
            events,
            min_evidence=2,
            min_sessions=2,
        )

        self.assertEqual(result["decision_count"], 3)
        self.assertEqual(result["covered_decision_count"], 1)
        self.assertEqual(result["learned_match_count"], 1)
        self.assertEqual(result["baseline_match_count"], 0)

    def test_profile_writer_uses_private_permissions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "profile.json"
            document = build_preference_profile([])

            write_profile(document, str(target))

            self.assertEqual(
                stat.S_IMODE(target.stat().st_mode),
                stat.S_IRUSR | stat.S_IWUSR,
            )
            self.assertEqual(json.loads(target.read_text()), document)

    def test_profile_builder_rejects_mixed_user_inputs(self):
        first = corrected_session("session:1", 1)
        second = corrected_session("session:2", 2)
        for item in second:
            item["user_profile_id"] = "profile:someone-else"

        with self.assertRaisesRegex(ValueError, "multiple user_profile_id"):
            build_preference_profile([*first, *second])


class MemoryInteractionLog:
    enabled = True

    def __init__(self):
        self.events = []

    def record(self, event_type, *, source, payload):
        event_id = f"event:{len(self.events) + 1}"
        self.events.append((event_type, source, dict(payload)))
        return event_id


class ActionablePreferenceController(PreferenceControllerMixin, ControllerBase):
    def normalize_grid_cells(self, cells):
        return list(cells or [])

    def is_valid_grid_index(self, index):
        return 0 <= int(index) < len(self.state.gridCells)

    def pick_grid_cell_visualization(self, cell_index, value=None, **_):
        cell = dict(self.state.gridCells[int(cell_index)] or {})
        cell["visualization_name"] = str(value or "")
        cell["selected_visualization"] = str(value or "")
        self.state.gridCells[int(cell_index)] = cell

    def set_active_grid_cell(self, cell_index, **_):
        self.state.activeGridCell = int(cell_index)


class PreferenceControllerTests(unittest.TestCase):
    def make_controller(self):
        events = []
        for day in range(1, 4):
            events.extend(corrected_session(f"session:{day}", day))
        profile = PreferenceProfile(build_preference_profile(events))
        state = SimpleNamespace()
        init_state(state, SimpleNamespace(ok=True, last_error=""))
        state.variableGroups = []
        state.queryAssistantAvailable = False
        state.queryAssistantProvider = ""
        state.gridCells[0].update(
            {
                "variable_id": "pressure",
                "variable_name": "pressure",
                "visualization_name": "heatmap",
                "selected_visualization": "heatmap",
                "visualization_options": ["heatmap", "scalar_field"],
                "status": "ready",
            }
        )
        recorder = MemoryInteractionLog()
        context = ControllerContext(
            server=SimpleNamespace(state=state, controller=SimpleNamespace()),
            backend=SimpleNamespace(),
            db=SimpleNamespace(),
            collection=SimpleNamespace(),
            parse_campaign=lambda *_args, **_kwargs: None,
            campaign_path="campaign.aca",
            interaction_log=recorder,
            preference_profile=profile,
            preference_mode="suggest",
            preference_status="Preference profile loaded",
        )
        return ActionablePreferenceController(context), recorder

    def test_suggestion_is_shown_and_applied_only_after_acceptance(self):
        controller, recorder = self.make_controller()

        controller.record_visualization_assignment(
            0,
            controller.state.gridCells[0],
            source="variable_add",
        )

        self.assertTrue(controller.state.showPreferenceSuggestion)
        self.assertEqual(
            controller.state.gridCells[0]["selected_visualization"], "heatmap"
        )
        self.assertIn("recommendation.shown", [event[0] for event in recorder.events])

        self.assertTrue(controller.accept_preference_suggestion())
        self.assertEqual(
            controller.state.gridCells[0]["selected_visualization"],
            "scalar_field",
        )
        self.assertFalse(controller.state.showPreferenceSuggestion)
        self.assertIn(
            "recommendation.accepted", [event[0] for event in recorder.events]
        )

    def test_shadow_mode_records_but_never_shows_or_applies(self):
        controller, recorder = self.make_controller()
        controller.preference_mode = "shadow"
        controller.state.preferenceMode = "shadow"

        controller.record_visualization_assignment(
            0,
            controller.state.gridCells[0],
            source="variable_add",
        )

        self.assertFalse(controller.state.showPreferenceSuggestion)
        self.assertEqual(
            controller.state.gridCells[0]["selected_visualization"], "heatmap"
        )
        self.assertIn(
            "recommendation.generated", [event[0] for event in recorder.events]
        )
        self.assertNotIn("recommendation.shown", [event[0] for event in recorder.events])


class ActionableWorkspacePreferenceController(
    PreferenceControllerMixin, ControllerBase
):
    def _stash_active_workspace_grid(self):
        layout = deepcopy(self.state.workspaceLayout)
        layout["panes"][0]["tabs"][0]["grid"]["cells"] = deepcopy(
            self.state.gridCells
        )
        self.state.workspaceLayout = layout
        return layout

    def capture_workspace_history(self):
        return {
            "layout": deepcopy(self.state.workspaceLayout),
            "cells": deepcopy(self.state.gridCells),
            "pane_id": self.state.workspaceActivePaneId,
            "tab_id": self.state.workspaceActiveTabId,
        }

    def restore_workspace_history(self, document):
        self.state.workspaceLayout = deepcopy(document["layout"])
        self.state.gridCells = deepcopy(document["cells"])
        self.state.workspaceActivePaneId = document["pane_id"]
        self.state.workspaceActiveTabId = document["tab_id"]

    def _workspace_variable_can_be_added(self, variable_id):
        return variable_id in self.state.variableNames

    def add_workspace_tab(self, pane_id="", **_):
        self.state.workspaceActivePaneId = str(pane_id or "pane-1")
        self.state.workspaceActiveTabId = "tab-suggested"
        self.state.gridCells = []

    def add_var_to_grid(self, variable_id, **_):
        self.state.gridCells.append(
            {
                "variable_id": variable_id,
                "selected_visualization": "heatmap",
            }
        )


class WorkspacePreferenceControllerTests(unittest.TestCase):
    def test_workspace_suggestion_creates_tab_only_after_acceptance(self):
        events = [
            saved_workspace("session:1", 1),
            saved_workspace("session:2", 2),
            saved_workspace("session:3", 3),
        ]
        profile = PreferenceProfile(build_preference_profile(events))
        state = SimpleNamespace()
        init_state(state, SimpleNamespace(ok=True, last_error=""))
        state.variableGroups = []
        state.variableNames = ["pressure", "temperature", "density"]
        state.queryAssistantAvailable = False
        state.queryAssistantProvider = ""
        recorder = MemoryInteractionLog()
        controller = ActionableWorkspacePreferenceController(
            ControllerContext(
                server=SimpleNamespace(state=state, controller=SimpleNamespace()),
                backend=SimpleNamespace(),
                db=SimpleNamespace(),
                collection=SimpleNamespace(),
                parse_campaign=lambda *_args, **_kwargs: None,
                campaign_path="campaign.aca",
                interaction_log=recorder,
                preference_profile=profile,
                preference_mode="suggest",
            )
        )

        self.assertTrue(controller.open_workspace_suggestion())
        self.assertEqual(controller.state.workspaceActiveTabId, "tab-1")
        self.assertTrue(controller.accept_preference_suggestion())

        self.assertEqual(controller.state.workspaceActiveTabId, "tab-suggested")
        self.assertEqual(
            {cell["variable_id"] for cell in controller.state.gridCells},
            {"pressure", "temperature", "density"},
        )
        self.assertIn(
            "recommendation.accepted", [event[0] for event in recorder.events]
        )


if __name__ == "__main__":
    unittest.main()
