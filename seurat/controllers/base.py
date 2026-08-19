"""Base state and dependencies for domain controller mixins."""

import time
from collections.abc import Mapping
from typing import Any, Dict, Optional

from application import SeuratApplication
from seurat.learning.context import (
    sanitized_query_context,
    sanitized_workspace_snapshot,
    query_feature_key,
    stable_fingerprint,
    workspace_location,
)
from seurat.learning.events import new_identifier
from seurat.models import grid_layout

from .context import ControllerContext


class ControllerBase:
    GRID_MIN_ROWS = grid_layout.GRID_MIN_ROWS
    GRID_MIN_COLS = grid_layout.GRID_MIN_COLS
    GRID_MAX_ROWS = grid_layout.GRID_MAX_ROWS
    GRID_MAX_COLS = grid_layout.GRID_MAX_COLS
    GRID_HEADER_HEIGHT = grid_layout.GRID_HEADER_HEIGHT
    GRID_MIN_TRACK_WEIGHT = grid_layout.GRID_MIN_TRACK_WEIGHT
    GRID_MAX_TRACK_WEIGHT = grid_layout.GRID_MAX_TRACK_WEIGHT

    def __init__(self, context: ControllerContext):
        self.context = context
        self.server = context.server
        self.state = context.server.state
        self.ctrl = context.server.controller
        self.backend = context.backend
        self.db = context.db
        self.collection = context.collection
        self.parse_campaign = context.parse_campaign
        self.campaign_path = context.campaign_path
        self.image_association_schema_path = context.image_association_schema_path
        self.campaign_schema_path = context.campaign_schema_path
        self.query_translator = context.query_translator
        self.interaction_log = context.interaction_log
        self.preference_profile = context.preference_profile
        self.preference_mode = context.preference_mode
        self.state.preferenceMode = str(context.preference_mode or "off")
        self.state.preferenceProfileLoaded = context.preference_profile is not None
        self.state.preferenceProfileStatus = str(context.preference_status or "")
        self.state.preferenceWorkspaceSuggestionsAvailable = bool(
            context.preference_profile is not None
            and getattr(context.preference_profile, "has_workspace_preferences", lambda: False)()
        )
        self._interaction_query_id = ""
        self._interaction_assignment_source = ""
        self._interaction_assignments: Dict[str, Dict[str, Any]] = {}
        self.state.queryAssistantAvailable = self.query_translator is not None
        self.state.queryAssistantProvider = (
            self.query_translator.description if self.query_translator else ""
        )
        self.application = SeuratApplication(backend=context.backend)
        self.plugin_source_variables_cache = {}

    def record_interaction(
        self,
        event_type: str,
        *,
        source: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> str:
        recorder = self.interaction_log
        if recorder is None or not bool(getattr(recorder, "enabled", False)):
            return ""
        try:
            return str(
                recorder.record(
                    event_type,
                    source=source,
                    payload=dict(payload or {}),
                )
                or ""
            )
        except Exception:
            return ""

    def record_query_applied(
        self,
        *,
        origin: str,
        target: str = "catalog",
        action_plan: Optional[Dict[str, Any]] = None,
    ) -> str:
        query_id = new_identifier("query")
        payload = sanitized_query_context(
            self.state,
            query_id=query_id,
            origin=origin,
            target=target,
            action_plan=action_plan,
        )
        event_id = self.record_interaction(
            "query.applied",
            source=origin,
            payload=payload,
        )
        if event_id:
            self._interaction_query_id = query_id
        return query_id if event_id else ""

    def interaction_workspace_location(
        self, cell_index: Optional[int] = None
    ) -> Dict[str, Any]:
        try:
            return workspace_location(self.state, cell_index)
        except Exception:
            return {}

    def interaction_workspace_snapshot(self) -> Dict[str, Any]:
        try:
            return sanitized_workspace_snapshot(self.state)
        except Exception:
            return {}

    def record_visualization_assignment(
        self,
        cell_index: int,
        cell: Dict[str, Any],
        *,
        source: str,
        selection_origin: str = "default",
    ) -> str:
        item = dict(cell or {})
        variable_id = str(
            item.get("variable_id", "") or item.get("variable_name", "") or ""
        )
        if not variable_id or str(item.get("status", "") or "") == "error":
            return ""
        visualization = str(
            item.get("selected_visualization", "")
            or item.get("visualization_name", "")
            or ""
        )
        candidates = [
            str(value or "")
            for value in list(item.get("visualization_options", []) or [])
            if str(value or "")
        ]
        if visualization and visualization not in candidates:
            candidates.append(visualization)
        payload = {
            "variable_id": variable_id,
            "candidate_visualizations": candidates,
            "selected_visualization": visualization,
            "selection_origin": str(selection_origin or "default"),
            "selection_policy": "heatmap_else_first",
            "query_id": self._interaction_query_id,
            "workspace": self.interaction_workspace_location(cell_index),
        }
        current_query = sanitized_query_context(
            self.state,
            query_id=self._interaction_query_id,
            origin="runtime",
            target="catalog",
        )
        current_query_key = query_feature_key(current_query)
        if current_query_key:
            payload["query_feature_key"] = current_query_key
        variable_features = self.interaction_variable_features(variable_id, item)
        if variable_features:
            payload["variable_features"] = variable_features
        source_identity = str(
            item.get("source_id", "") or item.get("_source_key", "") or ""
        )
        if source_identity:
            payload["source_id"] = stable_fingerprint(source_identity, "source")
        event_id = self.record_interaction(
            "visualization.assigned",
            source=source,
            payload=payload,
        )
        if event_id:
            self._interaction_assignments[self._interaction_cell_key(cell_index)] = {
                "event_id": event_id,
                "started": time.monotonic(),
            }
        preference_handler = getattr(
            self, "handle_visualization_assignment_for_preferences", None
        )
        if callable(preference_handler):
            try:
                preference_handler(
                    cell_index,
                    item,
                    assignment_event_id=event_id,
                    assignment_payload=payload,
                )
            except Exception:
                pass
        return event_id

    def interaction_variable_features(
        self, variable_id: str, cell: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Return bounded semantic features without copying campaign values."""

        item = dict(cell or {})
        catalog_item: Dict[str, Any] = {}
        for group in list(getattr(self.state, "variableGroups", []) or []):
            if not isinstance(group, Mapping):
                continue
            catalog_item = next(
                (
                    dict(variable)
                    for variable in list(group.get("variables", []) or [])
                    if isinstance(variable, Mapping)
                    and str(variable.get("id", "") or "") == str(variable_id or "")
                ),
                {},
            )
            if catalog_item:
                break

        features: Dict[str, Any] = {}
        variable_type = str(
            item.get("variable_type", "")
            or catalog_item.get("variable_type", "")
            or catalog_item.get("type", "")
            or ""
        ).strip()
        media_type = str(item.get("media_type", "") or "").strip()
        if variable_type:
            features["variable_type"] = variable_type[:80]
        if media_type:
            features["media_type"] = media_type[:80]

        metadata = item.get("metadata", {}) or catalog_item.get("metadata", {}) or {}
        if not isinstance(metadata, Mapping):
            metadata = {}
        raw_shape = metadata.get("Shape", catalog_item.get("shape", []))
        dimensions = []
        if isinstance(raw_shape, (list, tuple)):
            raw_dimensions = list(raw_shape)
        else:
            raw_dimensions = str(raw_shape or "").replace("x", ",").split(",")
        for raw_dimension in raw_dimensions:
            try:
                dimension = int(raw_dimension)
            except (TypeError, ValueError):
                continue
            if dimension >= 0:
                dimensions.append(dimension)
        if dimensions:
            features["dimensionality"] = len(dimensions)
            cardinality = 1
            for dimension in dimensions:
                cardinality *= max(1, dimension)
            if cardinality <= 1:
                features["shape_bucket"] = "scalar"
            elif cardinality <= 1_024:
                features["shape_bucket"] = "small"
            elif cardinality <= 1_048_576:
                features["shape_bucket"] = "medium"
            else:
                features["shape_bucket"] = "large"

        raw_steps = metadata.get(
            "AvailableStepsCount", catalog_item.get("steps_count", None)
        )
        if raw_steps not in (None, ""):
            try:
                features["time_varying"] = int(raw_steps) > 1
            except (TypeError, ValueError):
                pass
        return features

    def _interaction_cell_key(self, cell_index: int) -> str:
        location = self.interaction_workspace_location(cell_index)
        return "|".join(
            (
                str(location.get("pane_id", "") or ""),
                str(location.get("tab_id", "") or ""),
                str(location.get("cell_index", -1)),
            )
        )

    def interaction_assignment_reference(self, cell_index: int) -> Dict[str, Any]:
        item = dict(
            self._interaction_assignments.get(
                self._interaction_cell_key(cell_index), {}
            )
            or {}
        )
        if not item:
            return {}
        return {
            "assignment_event_id": str(item.get("event_id", "") or ""),
            "elapsed_since_assignment_ms": max(
                0, int((time.monotonic() - float(item.get("started", 0.0))) * 1000)
            ),
        }

    def clear_interaction_assignment(self, cell_index: Optional[int] = None) -> None:
        if cell_index is None:
            self._interaction_assignments.clear()
            return
        self._interaction_assignments.pop(
            self._interaction_cell_key(cell_index), None
        )
