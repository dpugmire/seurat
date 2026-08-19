"""Build versioned preference profiles from immutable interaction events."""

from collections import defaultdict
from datetime import datetime, timezone
from itertools import combinations
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Tuple

from .labels import variable_feature_key, visualization_preference_examples
from .profile import PREFERENCE_PROFILE_SCHEMA_VERSION


def _utc_timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _new_evidence() -> Dict[str, Any]:
    return {"wins": 0.0, "losses": 0.0, "sessions": set()}


def _add_evidence(
    collection: MutableMapping[str, Dict[str, Any]],
    visualization_id: str,
    session_id: str,
    *,
    wins: float = 0.0,
    losses: float = 0.0,
) -> None:
    if not visualization_id:
        return
    item = collection.setdefault(visualization_id, _new_evidence())
    item["wins"] += float(wins)
    item["losses"] += float(losses)
    if session_id:
        item["sessions"].add(session_id)


def _serialized_evidence(collection: Mapping[str, Mapping[str, Any]]) -> list:
    return [
        {
            "visualization_id": visualization_id,
            "wins": round(float(item.get("wins", 0.0) or 0.0), 6),
            "losses": round(float(item.get("losses", 0.0) or 0.0), 6),
            "sessions": sorted(item.get("sessions", set()) or set()),
        }
        for visualization_id, item in sorted(collection.items())
    ]


def _workspace_groups(
    events: Iterable[Mapping[str, Any]],
) -> Dict[Tuple[str, ...], Dict[str, Any]]:
    groups: Dict[Tuple[str, ...], Dict[str, Any]] = {}
    for event in events:
        event_type = str(event.get("event_type", "") or "")
        payload = event.get("payload", {}) or {}
        reason = str(payload.get("reason", "") or "") if isinstance(payload, Mapping) else ""
        if event_type != "workspace.saved" and not (
            event_type == "workspace.snapshot" and reason == "session_ended"
        ):
            continue
        workspace = payload.get("workspace", {}) if isinstance(payload, Mapping) else {}
        if not isinstance(workspace, Mapping):
            continue
        session_id = str(event.get("session_id", "") or "")
        for pane in list(workspace.get("panes", []) or []):
            if not isinstance(pane, Mapping):
                continue
            for tab in list(pane.get("tabs", []) or []):
                if not isinstance(tab, Mapping):
                    continue
                grid = tab.get("grid", {}) or {}
                cells = grid.get("cells", []) if isinstance(grid, Mapping) else []
                variables = tuple(
                    sorted(
                        {
                            str(cell.get("variable_id", "") or "")
                            for cell in list(cells or [])
                            if isinstance(cell, Mapping)
                            and str(cell.get("variable_id", "") or "")
                        }
                    )
                )
                if len(variables) < 2:
                    continue
                item = groups.setdefault(
                    variables, {"count": 0, "sessions": set()}
                )
                item["count"] += 1
                if session_id:
                    item["sessions"].add(session_id)
    return groups


def build_preference_profile(events: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    event_list = list(events)
    user_profile_ids = {
        str(event.get("user_profile_id", "") or "")
        for event in event_list
        if str(event.get("user_profile_id", "") or "")
    }
    if len(user_profile_ids) > 1:
        raise ValueError(
            "Preference profile input contains multiple user_profile_id values"
        )
    by_variable: Dict[str, Dict[str, Any]] = defaultdict(dict)
    by_query: Dict[Tuple[str, str], Dict[str, Any]] = defaultdict(dict)
    by_features: Dict[str, Dict[str, Any]] = defaultdict(dict)
    global_evidence: Dict[str, Any] = {}
    examples = visualization_preference_examples(event_list)
    for example in examples:
        if not example.variable_id:
            continue
        variable_evidence = by_variable[example.variable_id]
        query_evidence = (
            by_query[(example.variable_id, example.query_feature_key)]
            if example.query_feature_key
            else None
        )
        feature_key = variable_feature_key(example.variable_features)
        feature_evidence = by_features[feature_key] if feature_key else None
        if example.preferred_visualization:
            for collection in (
                variable_evidence,
                query_evidence,
                feature_evidence,
                global_evidence,
            ):
                if collection is not None:
                    _add_evidence(
                        collection,
                        example.preferred_visualization,
                        example.session_id,
                        wins=example.weight,
                    )
        for rejected in example.rejected_visualizations:
            for collection in (
                variable_evidence,
                query_evidence,
                feature_evidence,
                global_evidence,
            ):
                if collection is not None:
                    _add_evidence(
                        collection,
                        rejected,
                        example.session_id,
                        losses=example.weight,
                    )

    workspace_groups = _workspace_groups(event_list)
    return {
        "schema_version": PREFERENCE_PROFILE_SCHEMA_VERSION,
        "generated_at_utc": _utc_timestamp(),
        "source": {
            "user_profile_id": next(iter(user_profile_ids), ""),
            "event_schema_versions": sorted(
                {
                    int(event.get("schema_version", 0) or 0)
                    for event in event_list
                    if int(event.get("schema_version", 0) or 0) > 0
                }
            ),
            "event_count": len(event_list),
            "session_count": len(
                {
                    str(event.get("session_id", "") or "")
                    for event in event_list
                    if str(event.get("session_id", "") or "")
                }
            ),
            "preference_example_count": len(examples),
        },
        "visualization_preferences": {
            "query_groups": [
                {
                    "variable_id": variable_id,
                    "query_feature_key": query_key,
                    "visualizations": _serialized_evidence(evidence),
                }
                for (variable_id, query_key), evidence in sorted(by_query.items())
            ],
            "variables": [
                {
                    "variable_id": variable_id,
                    "visualizations": _serialized_evidence(evidence),
                }
                for variable_id, evidence in sorted(by_variable.items())
            ],
            "feature_groups": [
                {
                    "feature_key": feature_key,
                    "visualizations": _serialized_evidence(evidence),
                }
                for feature_key, evidence in sorted(by_features.items())
                if feature_key
            ],
            "global_visualizations": _serialized_evidence(global_evidence),
        },
        "workspace_preferences": {
            "groups": [
                {
                    "variables": list(variables),
                    "count": int(item["count"]),
                    "sessions": sorted(item["sessions"]),
                }
                for variables, item in sorted(
                    workspace_groups.items(),
                    key=lambda pair: (-pair[1]["count"], pair[0]),
                )
            ],
            "pair_counts": [
                {"variables": list(pair), "count": count}
                for pair, count in sorted(
                    _workspace_pair_counts(workspace_groups).items(),
                    key=lambda pair: (-pair[1], pair[0]),
                )
            ],
        },
    }


def _workspace_pair_counts(
    groups: Mapping[Tuple[str, ...], Mapping[str, Any]],
) -> Dict[Tuple[str, str], int]:
    counts: Dict[Tuple[str, str], int] = defaultdict(int)
    for variables, item in groups.items():
        for pair in combinations(variables, 2):
            counts[pair] += int(item.get("count", 0) or 0)
    return dict(counts)
