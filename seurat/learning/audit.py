"""Validate and summarize Seurat interaction JSONL logs."""

import argparse
from collections import Counter
from itertools import combinations
from typing import Any, Dict, Iterable, Iterator, Tuple

from .events import validate_event
from .io import decoded_lines, log_files


def _saved_colocations(snapshot: Any) -> Iterator[Tuple[str, str]]:
    if not isinstance(snapshot, dict):
        return
    for pane in snapshot.get("panes", []) or []:
        for tab in (pane or {}).get("tabs", []) or []:
            cells = ((tab or {}).get("grid", {}) or {}).get("cells", []) or []
            variables = sorted(
                {
                    str((cell or {}).get("variable_id", "") or "")
                    for cell in cells
                    if str((cell or {}).get("variable_id", "") or "")
                }
            )
            yield from combinations(variables, 2)


def audit_logs(paths: Iterable[str]) -> Dict[str, Any]:
    event_counts: Counter[str] = Counter()
    default_changes: Counter[Tuple[str, str]] = Counter()
    colocations: Counter[Tuple[str, str]] = Counter()
    sessions = set()
    valid_events = 0
    invalid_events = 0
    truncated_final_lines = 0

    files = log_files(paths)
    for path in files:
        for event, truncated in decoded_lines(path):
            if truncated:
                truncated_final_lines += 1
                continue
            if event is None or validate_event(event):
                invalid_events += 1
                continue
            valid_events += 1
            event_type = str(event["event_type"])
            event_counts[event_type] += 1
            sessions.add(str(event["session_id"]))
            payload = event.get("payload", {}) or {}
            if event_type == "visualization.changed":
                previous = str(payload.get("previous_visualization", "") or "")
                selected = str(payload.get("selected_visualization", "") or "")
                if previous and selected:
                    default_changes[(previous, selected)] += 1
            if event_type == "workspace.saved":
                colocations.update(_saved_colocations(payload.get("workspace")))

    return {
        "files": len(files),
        "sessions": len(sessions),
        "valid_events": valid_events,
        "invalid_events": invalid_events,
        "truncated_final_lines": truncated_final_lines,
        "event_counts": dict(event_counts),
        "default_changes": [
            {"from": source, "to": target, "count": count}
            for (source, target), count in default_changes.most_common()
        ],
        "saved_colocations": [
            {"variables": [first, second], "count": count}
            for (first, second), count in colocations.most_common()
        ],
    }


def format_audit(summary: Dict[str, Any]) -> str:
    counts = dict(summary.get("event_counts", {}) or {})
    lines = [
        f"Files: {int(summary.get('files', 0) or 0)}",
        f"Sessions: {int(summary.get('sessions', 0) or 0)}",
        f"Valid events: {int(summary.get('valid_events', 0) or 0)}",
        f"Invalid events: {int(summary.get('invalid_events', 0) or 0)}",
        f"Truncated final lines ignored: {int(summary.get('truncated_final_lines', 0) or 0)}",
        f"Queries applied: {int(counts.get('query.applied', 0) or 0)}",
        f"Visualizations assigned: {int(counts.get('visualization.assigned', 0) or 0)}",
        f"Manual visualization changes: {int(counts.get('visualization.changed', 0) or 0)}",
        f"Recommendations generated: {int(counts.get('recommendation.generated', 0) or 0)}",
        f"Recommendations accepted: {int(counts.get('recommendation.accepted', 0) or 0)}",
        f"Recommendations dismissed: {int(counts.get('recommendation.dismissed', 0) or 0)}",
        f"Saved workspace snapshots: {int(counts.get('workspace.saved', 0) or 0)}",
        "",
        "Most common visualization changes:",
    ]
    changes = list(summary.get("default_changes", []) or [])
    lines.extend(
        f"  {item['from']} -> {item['to']}: {item['count']}" for item in changes[:10]
    )
    if not changes:
        lines.append("  none")
    lines.extend(("", "Most common saved co-locations:"))
    colocations = list(summary.get("saved_colocations", []) or [])
    lines.extend(
        f"  {' + '.join(item['variables'])}: {item['count']}"
        for item in colocations[:10]
    )
    if not colocations:
        lines.append("  none")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate and summarize Seurat interaction JSONL logs."
    )
    parser.add_argument("paths", nargs="+", help="JSONL files or directories")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    print(format_audit(audit_logs(args.paths)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
