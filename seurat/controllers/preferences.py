"""Runtime preference ranking and explicit suggestion application."""

from collections.abc import Mapping
from typing import Any, Dict, List

from config import (
    SEURAT_PREFERENCE_MIN_CONFIDENCE,
    SEURAT_PREFERENCE_MIN_EVIDENCE,
    SEURAT_PREFERENCE_MIN_MARGIN,
    SEURAT_PREFERENCE_MIN_SESSIONS,
)
from query_parser import and_filter
from seurat.learning.events import new_identifier


class PreferenceControllerMixin:
    ACTION_BINDINGS = (
        ("accept_preference_suggestion", "accept_preference_suggestion"),
        ("dismiss_preference_suggestion", "dismiss_preference_suggestion"),
        ("choose_preference_alternative", "choose_preference_alternative"),
        ("open_workspace_suggestion", "open_workspace_suggestion"),
    )
    TRIGGER_BINDINGS = ()
    STATE_CHANGE_BINDINGS = ()
    HISTORY_ACTIONS = {
        "accept_preference_suggestion": "Apply preference suggestion",
    }
    HISTORY_TRIGGERS = {}

    def clear_preference_suggestion(self, *, keep_status: bool = False) -> None:
        self.state.showPreferenceSuggestion = False
        self.state.preferenceSuggestionId = ""
        self.state.preferenceSuggestionType = ""
        self.state.preferenceSuggestionTitle = ""
        self.state.preferenceSuggestionMessage = ""
        self.state.preferenceSuggestionVariableId = ""
        self.state.preferenceSuggestionCurrentVisualization = ""
        self.state.preferenceSuggestionRecommendedVisualization = ""
        self.state.preferenceSuggestionCellIndex = -1
        self.state.preferenceSuggestionPaneId = ""
        self.state.preferenceSuggestionTabId = ""
        self.state.preferenceSuggestionVariables = []
        self.state.preferenceSuggestionConfidence = 0.0
        self.state.preferenceSuggestionEvidenceCount = 0.0
        self.state.preferenceSuggestionSessionCount = 0
        if not keep_status:
            self.state.preferenceSuggestionStatus = ""

    def _recommendation_payload(self) -> Dict[str, Any]:
        payload = {
            "recommendation_id": str(self.state.preferenceSuggestionId or ""),
            "kind": str(self.state.preferenceSuggestionType or ""),
            "mode": str(self.preference_mode or "off"),
            "confidence": float(
                self.state.preferenceSuggestionConfidence or 0.0
            ),
            "evidence_count": float(
                self.state.preferenceSuggestionEvidenceCount or 0.0
            ),
            "session_count": int(
                self.state.preferenceSuggestionSessionCount or 0
            ),
            "profile_schema_version": int(
                getattr(self.preference_profile, "document", {}).get(
                    "schema_version", 0
                )
                if isinstance(
                    getattr(self.preference_profile, "document", {}), Mapping
                )
                else 0
            ),
        }
        variable_id = str(self.state.preferenceSuggestionVariableId or "")
        if variable_id:
            payload.update(
                {
                    "variable_id": variable_id,
                    "current_visualization": str(
                        self.state.preferenceSuggestionCurrentVisualization or ""
                    ),
                    "recommended_visualization": str(
                        self.state.preferenceSuggestionRecommendedVisualization or ""
                    ),
                    "workspace": {
                        "pane_id": str(
                            self.state.preferenceSuggestionPaneId or ""
                        ),
                        "tab_id": str(self.state.preferenceSuggestionTabId or ""),
                        "cell_index": int(
                            self.state.preferenceSuggestionCellIndex or 0
                        ),
                    },
                }
            )
        variables = [
            str(value or "")
            for value in list(self.state.preferenceSuggestionVariables or [])
            if str(value or "")
        ]
        if variables:
            payload["variables"] = variables
        return payload

    def _publish_visualization_suggestion(
        self,
        cell_index: int,
        cell: Mapping[str, Any],
        recommendation,
        *,
        assignment_event_id: str,
    ) -> None:
        variable_id = str(
            cell.get("variable_id", "") or cell.get("variable_name", "") or ""
        )
        current = str(
            cell.get("selected_visualization", "")
            or cell.get("visualization_name", "")
            or ""
        )
        self.clear_preference_suggestion()
        location = self.interaction_workspace_location(cell_index)
        self.state.preferenceSuggestionId = new_identifier("recommendation")
        self.state.preferenceSuggestionType = "visualization"
        self.state.preferenceSuggestionTitle = "Visualization suggestion"
        self.state.preferenceSuggestionMessage = (
            f"Based on {recommendation.evidence_count:g} preference signals "
            f"across {recommendation.session_count} sessions."
        )
        self.state.preferenceSuggestionVariableId = variable_id
        self.state.preferenceSuggestionCurrentVisualization = current
        self.state.preferenceSuggestionRecommendedVisualization = (
            recommendation.visualization_id
        )
        self.state.preferenceSuggestionCellIndex = int(cell_index)
        self.state.preferenceSuggestionPaneId = str(location.get("pane_id", "") or "")
        self.state.preferenceSuggestionTabId = str(location.get("tab_id", "") or "")
        self.state.preferenceSuggestionConfidence = float(
            recommendation.confidence
        )
        self.state.preferenceSuggestionEvidenceCount = float(
            recommendation.evidence_count
        )
        self.state.preferenceSuggestionSessionCount = int(
            recommendation.session_count
        )
        payload = self._recommendation_payload()
        payload.update(
            {
                "scope": str(recommendation.scope or ""),
                "assignment_event_id": str(assignment_event_id or ""),
                "query_id": self._interaction_query_id,
            }
        )
        self.record_interaction(
            "recommendation.generated",
            source="preference_policy",
            payload=payload,
        )
        if self.preference_mode == "suggest":
            self.state.showPreferenceSuggestion = True
            self.record_interaction(
                "recommendation.shown",
                source="preference_dialog",
                payload=self._recommendation_payload(),
            )

    def handle_visualization_assignment_for_preferences(
        self,
        cell_index: int,
        cell: Mapping[str, Any],
        *,
        assignment_event_id: str = "",
        assignment_payload: Mapping[str, Any] | None = None,
    ) -> None:
        profile = self.preference_profile
        if (
            profile is None
            or self.preference_mode not in {"shadow", "suggest"}
            or bool(getattr(self, "_preference_suggestions_suspended", False))
        ):
            return
        payload = dict(assignment_payload or {})
        variable_id = str(payload.get("variable_id", "") or "")
        candidates = list(payload.get("candidate_visualizations", []) or [])
        current = str(payload.get("selected_visualization", "") or "")
        recommendation = profile.recommend_visualization(
            variable_id,
            candidates,
            variable_features=payload.get("variable_features", {}),
            query_feature_key=str(payload.get("query_feature_key", "") or ""),
            min_evidence=SEURAT_PREFERENCE_MIN_EVIDENCE,
            min_sessions=SEURAT_PREFERENCE_MIN_SESSIONS,
            min_confidence=SEURAT_PREFERENCE_MIN_CONFIDENCE,
            min_margin=SEURAT_PREFERENCE_MIN_MARGIN,
        )
        if recommendation is None or recommendation.visualization_id == current:
            return
        self._publish_visualization_suggestion(
            cell_index,
            cell,
            recommendation,
            assignment_event_id=assignment_event_id,
        )

    def _fail_preference_suggestion(self, message: str) -> bool:
        self.state.preferenceSuggestionStatus = str(message or "")
        payload = self._recommendation_payload()
        payload["reason"] = str(message or "")[:240]
        self.record_interaction(
            "recommendation.failed",
            source="preference_dialog",
            payload=payload,
        )
        return False

    def _accept_visualization_suggestion(self) -> bool:
        try:
            cell_index = int(self.state.preferenceSuggestionCellIndex)
        except (TypeError, ValueError):
            return self._fail_preference_suggestion("The target cell is invalid.")
        location = self.interaction_workspace_location(cell_index)
        if (
            str(location.get("pane_id", "") or "")
            != str(self.state.preferenceSuggestionPaneId or "")
            or str(location.get("tab_id", "") or "")
            != str(self.state.preferenceSuggestionTabId or "")
            or not self.is_valid_grid_index(cell_index)
        ):
            return self._fail_preference_suggestion(
                "The target workspace cell is no longer active."
            )
        cells = self.normalize_grid_cells(self.state.gridCells)
        cell = dict(cells[cell_index] or {})
        variable_id = str(
            cell.get("variable_id", "") or cell.get("variable_name", "") or ""
        )
        current = str(
            cell.get("selected_visualization", "")
            or cell.get("visualization_name", "")
            or ""
        )
        recommended = str(
            self.state.preferenceSuggestionRecommendedVisualization or ""
        )
        candidates = [
            str(value or "")
            for value in list(cell.get("visualization_options", []) or [])
        ]
        if (
            variable_id != str(self.state.preferenceSuggestionVariableId or "")
            or current != str(
                self.state.preferenceSuggestionCurrentVisualization or ""
            )
            or recommended not in candidates
        ):
            return self._fail_preference_suggestion(
                "The visualization choices changed; generate a new suggestion."
            )

        previous_source = getattr(
            self, "_interaction_visualization_change_source", ""
        )
        self._interaction_visualization_change_source = "preference_suggestion"
        try:
            self.pick_grid_cell_visualization(cell_index, recommended)
        finally:
            self._interaction_visualization_change_source = previous_source
        updated = dict(list(self.state.gridCells or [])[cell_index] or {})
        selected = str(
            updated.get("selected_visualization", "")
            or updated.get("visualization_name", "")
            or ""
        )
        if selected != recommended or str(updated.get("status", "") or "") == "error":
            return self._fail_preference_suggestion(
                "Seurat could not apply the recommended visualization."
            )
        self.record_interaction(
            "recommendation.accepted",
            source="preference_dialog",
            payload=self._recommendation_payload(),
        )
        self.clear_preference_suggestion()
        return True

    def _workspace_tabs(self, layout: Mapping[str, Any]) -> List[List[str]]:
        tabs = []
        for pane in list(layout.get("panes", []) or []):
            if not isinstance(pane, Mapping):
                continue
            for tab in list(pane.get("tabs", []) or []):
                if not isinstance(tab, Mapping):
                    continue
                grid = tab.get("grid", {}) or {}
                cells = grid.get("cells", []) if isinstance(grid, Mapping) else []
                tabs.append(
                    list(
                        dict.fromkeys(
                            str(cell.get("variable_id", "") or "")
                            for cell in list(cells or [])
                            if isinstance(cell, Mapping)
                            and str(cell.get("variable_id", "") or "")
                        )
                    )
                )
        return tabs

    def open_workspace_suggestion(self, **_) -> bool:
        profile = self.preference_profile
        if profile is None or self.preference_mode != "suggest":
            self.state.preferenceSuggestionStatus = (
                "Workspace suggestions require a loaded profile in suggest mode."
            )
            return False
        layout = self._stash_active_workspace_grid()
        recommendation = profile.recommend_workspace(
            existing_tabs=self._workspace_tabs(layout),
            available_variables=list(self.state.variableNames or []),
            min_evidence=max(2, int(SEURAT_PREFERENCE_MIN_EVIDENCE)),
            min_sessions=SEURAT_PREFERENCE_MIN_SESSIONS,
        )
        if recommendation is None:
            self.state.preferenceSuggestionStatus = (
                "No workspace suggestion has enough new evidence yet."
            )
            return False
        self.clear_preference_suggestion()
        self.state.preferenceSuggestionId = new_identifier("recommendation")
        self.state.preferenceSuggestionType = "workspace"
        self.state.preferenceSuggestionTitle = "Workspace suggestion"
        self.state.preferenceSuggestionMessage = (
            "Create a new tab containing variables that commonly appeared "
            "together in saved workspaces."
        )
        self.state.preferenceSuggestionVariables = list(recommendation.variables)
        self.state.preferenceSuggestionConfidence = recommendation.confidence
        self.state.preferenceSuggestionEvidenceCount = recommendation.evidence_count
        self.state.preferenceSuggestionSessionCount = recommendation.session_count
        self.state.showPreferenceSuggestion = True
        payload = self._recommendation_payload()
        self.record_interaction(
            "recommendation.generated",
            source="preference_policy",
            payload=payload,
        )
        self.record_interaction(
            "recommendation.shown",
            source="preference_dialog",
            payload=payload,
        )
        return True

    def _workspace_variable_can_be_added(self, variable_id: str) -> bool:
        source_filter = self.active_source_filter_for_variable(variable_id)
        query_filter = self.active_query_filter()
        active_filter = (
            and_filter(query_filter, source_filter)
            if query_filter and source_filter
            else (query_filter or source_filter or None)
        )
        if self.visualization_names_with_plugins(
            variable_id,
            source_filter=source_filter or None,
            extra_filter=active_filter,
        ):
            return True
        if self.normalize_scalar_plot_policy() != "always":
            return False
        try:
            return bool(
                self.db.scalar_plot_candidate(
                    variable_id,
                    source_filter=source_filter or None,
                    extra_filter=query_filter,
                )
            )
        except Exception:
            return False

    def _accept_workspace_suggestion(self) -> bool:
        variables = [
            str(value or "")
            for value in list(self.state.preferenceSuggestionVariables or [])
            if str(value or "")
        ]
        available = {str(value or "") for value in list(self.state.variableNames or [])}
        if len(variables) < 2 or any(value not in available for value in variables):
            return self._fail_preference_suggestion(
                "The suggested variables are no longer available."
            )
        unavailable = [
            variable
            for variable in variables
            if not self._workspace_variable_can_be_added(variable)
        ]
        if unavailable:
            return self._fail_preference_suggestion(
                "Some suggested variables require unavailable or manually "
                "confirmed visualizations: " + ", ".join(unavailable)
            )

        pane_id = str(self.state.workspaceActivePaneId or "")
        previous_source = self._interaction_assignment_source
        previous_suspension = bool(
            getattr(self, "_preference_suggestions_suspended", False)
        )
        previous_workspace = self.capture_workspace_history()
        self._interaction_assignment_source = "preference_workspace_suggestion"
        self._preference_suggestions_suspended = True
        try:
            self.add_workspace_tab(pane_id)
            new_pane_id = str(self.state.workspaceActivePaneId or "")
            new_tab_id = str(self.state.workspaceActiveTabId or "")
            for variable in variables:
                self.add_var_to_grid(variable)
        except Exception as error:
            self.restore_workspace_history(previous_workspace)
            return self._fail_preference_suggestion(
                "Seurat could not create the suggested workspace: "
                f"{type(error).__name__}: {error}"
            )
        finally:
            self._interaction_assignment_source = previous_source
            self._preference_suggestions_suspended = previous_suspension

        placed = {
            str(cell.get("variable_id", "") or "")
            for cell in list(self.state.gridCells or [])
            if isinstance(cell, Mapping)
        }
        if not set(variables).issubset(placed):
            self.restore_workspace_history(previous_workspace)
            return self._fail_preference_suggestion(
                "Seurat could not populate every suggested variable."
            )
        payload = self._recommendation_payload()
        payload["workspace"] = {
            "pane_id": new_pane_id,
            "tab_id": new_tab_id,
        }
        self.record_interaction(
            "recommendation.accepted",
            source="preference_dialog",
            payload=payload,
        )
        self.clear_preference_suggestion()
        return True

    def accept_preference_suggestion(self, **_) -> bool:
        kind = str(self.state.preferenceSuggestionType or "")
        if kind == "visualization":
            return self._accept_visualization_suggestion()
        if kind == "workspace":
            return self._accept_workspace_suggestion()
        return False

    def dismiss_preference_suggestion(self, reason: str = "dismissed", **_) -> None:
        if not str(self.state.preferenceSuggestionId or ""):
            self.clear_preference_suggestion()
            return
        payload = self._recommendation_payload()
        payload["reason"] = str(reason or "dismissed")[:80]
        self.record_interaction(
            "recommendation.dismissed",
            source="preference_dialog",
            payload=payload,
        )
        self.clear_preference_suggestion()

    def choose_preference_alternative(self, **_) -> None:
        try:
            cell_index = int(self.state.preferenceSuggestionCellIndex)
        except (TypeError, ValueError):
            cell_index = -1
        self.dismiss_preference_suggestion(reason="choose_alternative")
        if self.is_valid_grid_index(cell_index):
            self.set_active_grid_cell(cell_index)
