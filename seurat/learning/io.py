"""Shared readers for append-only Seurat interaction logs."""

import json
from pathlib import Path
from typing import Any, Iterable, Iterator, List, Tuple

from .events import validate_event


def log_files(paths: Iterable[str]) -> List[Path]:
    files: List[Path] = []
    for raw_path in paths:
        path = Path(raw_path).expanduser()
        if path.is_dir():
            files.extend(sorted(path.glob("*.jsonl")))
        elif path.is_file():
            files.append(path)
    return sorted(dict.fromkeys(files))


def decoded_lines(path: Path) -> Iterator[Tuple[Any, bool]]:
    """Yield decoded values and whether an invalid value is a truncated tail."""

    content = path.read_bytes()
    lines = content.splitlines(keepends=True)
    for index, raw_line in enumerate(lines):
        complete = raw_line.endswith((b"\n", b"\r"))
        text = raw_line.decode("utf-8", errors="replace").strip()
        if not text:
            continue
        try:
            yield json.loads(text), False
        except json.JSONDecodeError:
            yield None, index == len(lines) - 1 and not complete


def valid_events(paths: Iterable[str]) -> List[dict]:
    """Return schema-valid events in deterministic session/event order."""

    events = []
    for path in log_files(paths):
        for event, truncated in decoded_lines(path):
            if truncated or event is None or validate_event(event):
                continue
            events.append(dict(event))
    return sorted(
        events,
        key=lambda item: (
            str(item.get("timestamp_utc", "") or ""),
            str(item.get("session_id", "") or ""),
            int(item.get("event_sequence", 0) or 0),
        ),
    )
