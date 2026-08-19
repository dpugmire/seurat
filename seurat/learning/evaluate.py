"""Chronological offline evaluation for learned visualization preferences."""

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

from .builder import build_preference_profile
from .io import valid_events
from .labels import visualization_preference_examples
from .profile import PreferenceProfile


def evaluate_events(
    events: Iterable[Mapping[str, Any]],
    *,
    min_evidence: float = 3.0,
    min_sessions: int = 2,
    min_confidence: float = 0.67,
    min_margin: float = 0.15,
) -> Dict[str, Any]:
    """Evaluate each session using only events from earlier sessions."""

    event_list = list(events)
    user_profile_ids = {
        str(event.get("user_profile_id", "") or "")
        for event in event_list
        if str(event.get("user_profile_id", "") or "")
    }
    if len(user_profile_ids) > 1:
        raise ValueError(
            "Evaluation input contains multiple user_profile_id values"
        )
    sessions: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for event in event_list:
        session_id = str(event.get("session_id", "") or "")
        if session_id:
            sessions[session_id].append(event)
    ordered_sessions = sorted(
        sessions.items(),
        key=lambda pair: min(
            str(event.get("timestamp_utc", "") or "") for event in pair[1]
        ),
    )

    training_events: List[Mapping[str, Any]] = []
    decision_count = 0
    correction_count = 0
    covered = 0
    learned_matches = 0
    baseline_matches = 0
    baseline_decisions = 0
    per_variable: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {"decisions": 0, "covered": 0, "matches": 0}
    )

    for _session_id, session_events in ordered_sessions:
        examples = [
            example
            for example in visualization_preference_examples(session_events)
            if example.preferred_visualization
        ]
        profile = PreferenceProfile(build_preference_profile(training_events))
        for example in examples:
            decision_count += 1
            variable = per_variable[example.variable_id]
            variable["decisions"] += 1
            if example.reason == "manual_correction":
                correction_count += 1
            if example.baseline_visualization:
                baseline_decisions += 1
                if example.baseline_visualization == example.preferred_visualization:
                    baseline_matches += 1
            recommendation = profile.recommend_visualization(
                example.variable_id,
                example.candidates,
                variable_features=example.variable_features,
                query_feature_key=example.query_feature_key,
                min_evidence=min_evidence,
                min_sessions=min_sessions,
                min_confidence=min_confidence,
                min_margin=min_margin,
            )
            if recommendation is None:
                continue
            covered += 1
            variable["covered"] += 1
            if recommendation.visualization_id == example.preferred_visualization:
                learned_matches += 1
                variable["matches"] += 1
        training_events.extend(session_events)

    return {
        "strategy": "walk-forward-by-session",
        "session_count": len(ordered_sessions),
        "decision_count": decision_count,
        "explicit_correction_count": correction_count,
        "covered_decision_count": covered,
        "abstained_decision_count": decision_count - covered,
        "learned_match_count": learned_matches,
        "learned_agreement": learned_matches / covered if covered else None,
        "coverage": covered / decision_count if decision_count else None,
        "baseline_decision_count": baseline_decisions,
        "baseline_match_count": baseline_matches,
        "baseline_agreement": (
            baseline_matches / baseline_decisions if baseline_decisions else None
        ),
        "thresholds": {
            "min_evidence": min_evidence,
            "min_sessions": min_sessions,
            "min_confidence": min_confidence,
            "min_margin": min_margin,
        },
        "variables": [
            {"variable_id": variable_id, **counts}
            for variable_id, counts in sorted(per_variable.items())
        ],
    }


def _percentage(value: Any) -> str:
    return "n/a" if value is None else f"{100.0 * float(value):.1f}%"


def format_evaluation(result: Mapping[str, Any]) -> str:
    return "\n".join(
        (
            f"Strategy: {result.get('strategy', '')}",
            f"Sessions: {int(result.get('session_count', 0) or 0)}",
            f"Explicit decisions: {int(result.get('decision_count', 0) or 0)}",
            f"Explicit corrections: {int(result.get('explicit_correction_count', 0) or 0)}",
            f"Recommendation coverage: {_percentage(result.get('coverage'))}",
            f"Learned agreement when covered: {_percentage(result.get('learned_agreement'))}",
            "Existing-policy agreement on corrected decisions: "
            f"{_percentage(result.get('baseline_agreement'))}",
            f"Abstentions: {int(result.get('abstained_decision_count', 0) or 0)}",
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Walk-forward evaluation of Seurat preference logs."
    )
    parser.add_argument("paths", nargs="+", help="Interaction log files/directories")
    parser.add_argument("--min-evidence", type=float, default=3.0)
    parser.add_argument("--min-sessions", type=int, default=2)
    parser.add_argument("--min-confidence", type=float, default=0.67)
    parser.add_argument("--min-margin", type=float, default=0.15)
    parser.add_argument("--output", default="", help="Optional JSON report path")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = evaluate_events(
            valid_events(args.paths),
            min_evidence=args.min_evidence,
            min_sessions=args.min_sessions,
            min_confidence=args.min_confidence,
            min_margin=args.min_margin,
        )
    except ValueError as error:
        parser.error(str(error))
    print(format_evaluation(result))
    if args.output:
        target = Path(args.output).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
