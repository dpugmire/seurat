"""Versioned local preference profile and conservative recommendation policy."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from .labels import normalized_variable_features, variable_feature_key


PREFERENCE_PROFILE_SCHEMA_VERSION = 1
PREFERENCE_MODES = frozenset({"off", "shadow", "suggest"})


def normalize_preference_mode(value: Any) -> str:
    mode = str(value or "off").strip().lower()
    return mode if mode in PREFERENCE_MODES else "off"


@dataclass(frozen=True)
class VisualizationRecommendation:
    visualization_id: str
    confidence: float
    margin: float
    evidence_count: float
    session_count: int
    scope: str


@dataclass(frozen=True)
class WorkspaceRecommendation:
    variables: Tuple[str, ...]
    confidence: float
    evidence_count: int
    session_count: int


def _visualization_entries(value: Any) -> Dict[str, Dict[str, Any]]:
    if not isinstance(value, list):
        return {}
    entries = {}
    for item in value:
        if not isinstance(item, Mapping):
            continue
        visualization_id = str(item.get("visualization_id", "") or "").strip()
        if not visualization_id:
            continue
        try:
            wins = max(0.0, float(item.get("wins", 0.0) or 0.0))
            losses = max(0.0, float(item.get("losses", 0.0) or 0.0))
        except (TypeError, ValueError):
            continue
        sessions = tuple(
            sorted(
                {
                    str(session or "")
                    for session in list(item.get("sessions", []) or [])
                    if str(session or "")
                }
            )
        )
        entries[visualization_id] = {
            "wins": wins,
            "losses": losses,
            "sessions": sessions,
        }
    return entries


class PreferenceProfile:
    """Validated read-only preference evidence used by runtime ranking."""

    def __init__(self, document: Mapping[str, Any], *, source_path: str = ""):
        if int(document.get("schema_version", 0) or 0) != PREFERENCE_PROFILE_SCHEMA_VERSION:
            raise ValueError(
                "Unsupported preference profile schema version: "
                f"{document.get('schema_version')}"
            )
        preferences = document.get("visualization_preferences", {}) or {}
        if not isinstance(preferences, Mapping):
            raise ValueError("visualization_preferences must be an object")

        self.document = dict(document)
        self.source_path = str(source_path or "")
        source = document.get("source", {}) or {}
        self.user_profile_id = (
            str(source.get("user_profile_id", "") or "")
            if isinstance(source, Mapping)
            else ""
        )
        self.variables: Dict[str, Dict[str, Dict[str, Any]]] = {}
        for item in list(preferences.get("variables", []) or []):
            if not isinstance(item, Mapping):
                continue
            variable_id = str(item.get("variable_id", "") or "").strip()
            entries = _visualization_entries(item.get("visualizations"))
            if variable_id and entries:
                self.variables[variable_id] = entries

        self.query_groups: Dict[Tuple[str, str], Dict[str, Dict[str, Any]]] = {}
        for item in list(preferences.get("query_groups", []) or []):
            if not isinstance(item, Mapping):
                continue
            variable_id = str(item.get("variable_id", "") or "").strip()
            query_key = str(item.get("query_feature_key", "") or "").strip()
            entries = _visualization_entries(item.get("visualizations"))
            if variable_id and query_key and entries:
                self.query_groups[(variable_id, query_key)] = entries

        self.feature_groups: Dict[str, Dict[str, Dict[str, Any]]] = {}
        for item in list(preferences.get("feature_groups", []) or []):
            if not isinstance(item, Mapping):
                continue
            key = str(item.get("feature_key", "") or "").strip()
            entries = _visualization_entries(item.get("visualizations"))
            if key and entries:
                self.feature_groups[key] = entries

        self.global_visualizations = _visualization_entries(
            preferences.get("global_visualizations")
        )
        workspace = document.get("workspace_preferences", {}) or {}
        self.workspace_groups = []
        if isinstance(workspace, Mapping):
            for item in list(workspace.get("groups", []) or []):
                if not isinstance(item, Mapping):
                    continue
                variables = tuple(
                    dict.fromkeys(
                        text
                        for value in list(item.get("variables", []) or [])
                        if (text := str(value or "").strip())
                    )
                )
                try:
                    count = max(0, int(item.get("count", 0) or 0))
                except (TypeError, ValueError):
                    continue
                sessions = tuple(
                    sorted(
                        {
                            str(value or "")
                            for value in list(item.get("sessions", []) or [])
                            if str(value or "")
                        }
                    )
                )
                if len(variables) >= 2 and count:
                    self.workspace_groups.append(
                        {
                            "variables": variables,
                            "count": count,
                            "sessions": sessions,
                        }
                    )

    @classmethod
    def load(cls, path: str) -> "PreferenceProfile":
        source = Path(str(path or "")).expanduser()
        if not str(path or "").strip():
            raise ValueError("Preference profile path is empty")
        document = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(document, Mapping):
            raise ValueError("Preference profile must be a JSON object")
        return cls(document, source_path=str(source))

    def recommend_visualization(
        self,
        variable_id: str,
        candidates: Sequence[str],
        *,
        variable_features: Optional[Mapping[str, Any]] = None,
        query_feature_key: str = "",
        min_evidence: float = 3.0,
        min_sessions: int = 2,
        min_confidence: float = 0.67,
        min_margin: float = 0.15,
    ) -> Optional[VisualizationRecommendation]:
        available = tuple(
            dict.fromkeys(
                text
                for value in list(candidates or [])
                if (text := str(value or "").strip())
            )
        )
        if len(available) < 2:
            return None

        variable_key = str(variable_id or "").strip()
        feature_key = variable_feature_key(variable_features or {})
        scopes = (
            (
                "query",
                self.query_groups.get(
                    (variable_key, str(query_feature_key or "")), {}
                ),
            ),
            ("variable", self.variables.get(variable_key, {})),
            ("features", self.feature_groups.get(feature_key, {})),
            ("global", self.global_visualizations),
        )
        for scope, evidence in scopes:
            scored = []
            for candidate in available:
                item = evidence.get(candidate, {})
                wins = float(item.get("wins", 0.0) or 0.0)
                losses = float(item.get("losses", 0.0) or 0.0)
                count = wins + losses
                confidence = (wins + 1.0) / (count + 2.0)
                sessions = len(tuple(item.get("sessions", ()) or ()))
                scored.append((confidence, count, sessions, candidate))
            scored.sort(key=lambda item: (-item[0], -item[1], item[3]))
            best = scored[0]
            second = scored[1]
            margin = best[0] - second[0]
            if not any(item[1] > 0 for item in scored):
                continue
            if (
                best[1] < float(min_evidence)
                or best[2] < int(min_sessions)
            ):
                continue
            if best[0] >= float(min_confidence) and margin >= float(min_margin):
                return VisualizationRecommendation(
                    visualization_id=best[3],
                    confidence=best[0],
                    margin=margin,
                    evidence_count=best[1],
                    session_count=best[2],
                    scope=scope,
                )
            return None
        return None

    def recommend_workspace(
        self,
        *,
        existing_tabs: Iterable[Iterable[str]],
        available_variables: Iterable[str],
        min_evidence: int = 2,
        min_sessions: int = 2,
    ) -> Optional[WorkspaceRecommendation]:
        existing = [
            {str(value or "") for value in tab if str(value or "")}
            for tab in existing_tabs
        ]
        available = {
            str(value or "") for value in available_variables if str(value or "")
        }
        candidates = []
        for item in self.workspace_groups:
            variables = tuple(item["variables"])
            variable_set = set(variables)
            session_count = len(item["sessions"])
            if (
                item["count"] < int(min_evidence)
                or session_count < int(min_sessions)
                or not variable_set.issubset(available)
                or any(variable_set.issubset(tab) for tab in existing)
            ):
                continue
            candidates.append(
                WorkspaceRecommendation(
                    variables=variables,
                    confidence=item["count"] / (item["count"] + 1.0),
                    evidence_count=item["count"],
                    session_count=session_count,
                )
            )
        if not candidates:
            return None
        return sorted(
            candidates,
            key=lambda item: (
                -item.confidence,
                -item.session_count,
                -len(item.variables),
                item.variables,
            ),
        )[0]

    def has_workspace_preferences(self) -> bool:
        return bool(self.workspace_groups)

    def feature_key(self, features: Mapping[str, Any]) -> str:
        return variable_feature_key(normalized_variable_features(features))
