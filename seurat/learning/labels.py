"""Turn semantic interaction events into conservative preference labels."""

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Tuple


MANUAL_SELECTION_ORIGINS = frozenset(
    {
        "manual",
        "grid_menu",
        "source_preview_menu",
        "preference_suggestion",
    }
)
QUICK_REMOVAL_MILLISECONDS = 30_000


def _text_list(value: Any) -> Tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(
        dict.fromkeys(
            text
            for item in value
            if (text := str(item or "").strip())
        )
    )


def normalized_variable_features(value: Any) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    features = {}
    for key in (
        "variable_type",
        "media_type",
        "dimensionality",
        "shape_bucket",
        "time_varying",
    ):
        item = value.get(key)
        if isinstance(item, bool):
            features[key] = item
        elif isinstance(item, int) and not isinstance(item, bool):
            features[key] = item
        elif isinstance(item, str) and item.strip():
            features[key] = item.strip()[:80]
    return features


def variable_feature_key(features: Mapping[str, Any]) -> str:
    values = normalized_variable_features(features)
    if not values:
        return ""
    return "|".join(f"{key}={values[key]}" for key in sorted(values))


@dataclass(frozen=True)
class PreferenceExample:
    session_id: str
    timestamp_utc: str
    event_id: str
    variable_id: str
    candidates: Tuple[str, ...]
    baseline_visualization: str
    preferred_visualization: str
    rejected_visualizations: Tuple[str, ...]
    query_id: str
    query_feature_key: str
    variable_features: Dict[str, Any]
    weight: float
    reason: str


def visualization_preference_examples(
    events: Iterable[Mapping[str, Any]],
) -> List[PreferenceExample]:
    """Extract explicit choices, corrections, and quick-removal negatives."""

    assignments: Dict[str, Mapping[str, Any]] = {}
    examples: List[PreferenceExample] = []
    for event in events:
        event_type = str(event.get("event_type", "") or "")
        payload = event.get("payload", {}) or {}
        if not isinstance(payload, Mapping):
            continue
        event_id = str(event.get("event_id", "") or "")
        if event_type == "visualization.assigned":
            if event_id:
                assignments[event_id] = event
            origin = str(payload.get("selection_origin", "") or "")
            selected = str(payload.get("selected_visualization", "") or "")
            candidates = _text_list(payload.get("candidate_visualizations"))
            if origin not in MANUAL_SELECTION_ORIGINS or not selected:
                continue
            rejected = tuple(item for item in candidates if item != selected)
            if not rejected:
                continue
            examples.append(
                PreferenceExample(
                    session_id=str(event.get("session_id", "") or ""),
                    timestamp_utc=str(event.get("timestamp_utc", "") or ""),
                    event_id=event_id,
                    variable_id=str(payload.get("variable_id", "") or ""),
                    candidates=candidates,
                    baseline_visualization="",
                    preferred_visualization=selected,
                    rejected_visualizations=rejected,
                    query_id=str(payload.get("query_id", "") or ""),
                    query_feature_key=str(
                        payload.get("query_feature_key", "") or ""
                    ),
                    variable_features=normalized_variable_features(
                        payload.get("variable_features")
                    ),
                    weight=1.0,
                    reason="explicit_selection",
                )
            )
            continue

        if event_type not in {"visualization.changed", "visualization.removed"}:
            continue
        assignment_id = str(payload.get("assignment_event_id", "") or "")
        assignment = assignments.get(assignment_id, {})
        assignment_payload = assignment.get("payload", {}) or {}
        variable_id = str(
            payload.get("variable_id", "")
            or assignment_payload.get("variable_id", "")
            or ""
        )
        candidates = _text_list(
            payload.get("candidate_visualizations")
            or assignment_payload.get("candidate_visualizations")
        )
        features = normalized_variable_features(
            payload.get("variable_features")
            or assignment_payload.get("variable_features")
        )
        query_id = str(
            payload.get("query_id", "")
            or assignment_payload.get("query_id", "")
            or ""
        )
        query_key = str(
            payload.get("query_feature_key", "")
            or assignment_payload.get("query_feature_key", "")
            or ""
        )
        if event_type == "visualization.changed":
            previous = str(payload.get("previous_visualization", "") or "")
            selected = str(payload.get("selected_visualization", "") or "")
            if not variable_id or not previous or not selected or previous == selected:
                continue
            candidates = tuple(dict.fromkeys((*candidates, previous, selected)))
            examples.append(
                PreferenceExample(
                    session_id=str(event.get("session_id", "") or ""),
                    timestamp_utc=str(event.get("timestamp_utc", "") or ""),
                    event_id=event_id,
                    variable_id=variable_id,
                    candidates=candidates,
                    baseline_visualization=previous,
                    preferred_visualization=selected,
                    rejected_visualizations=(previous,),
                    query_id=query_id,
                    query_feature_key=query_key,
                    variable_features=features,
                    weight=1.0,
                    reason="manual_correction",
                )
            )
            continue

        visualization = str(payload.get("visualization_id", "") or "")
        try:
            elapsed = int(payload.get("elapsed_since_assignment_ms", -1))
        except (TypeError, ValueError):
            elapsed = -1
        if (
            variable_id
            and visualization
            and 0 <= elapsed <= QUICK_REMOVAL_MILLISECONDS
        ):
            candidates = tuple(dict.fromkeys((*candidates, visualization)))
            examples.append(
                PreferenceExample(
                    session_id=str(event.get("session_id", "") or ""),
                    timestamp_utc=str(event.get("timestamp_utc", "") or ""),
                    event_id=event_id,
                    variable_id=variable_id,
                    candidates=candidates,
                    baseline_visualization=visualization,
                    preferred_visualization="",
                    rejected_visualizations=(visualization,),
                    query_id=query_id,
                    query_feature_key=query_key,
                    variable_features=features,
                    weight=0.5,
                    reason="quick_removal",
                )
            )
    return examples
