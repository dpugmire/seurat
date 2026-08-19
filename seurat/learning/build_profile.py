"""CLI for deriving a local preference profile from interaction logs."""

import argparse
import json
import os
from pathlib import Path
from uuid import uuid4

from .builder import build_preference_profile
from .io import valid_events


def write_profile(document, output_path: str) -> Path:
    target = Path(output_path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
    descriptor = os.open(
        str(temporary),
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(document, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except Exception:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise
    return target


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a versioned Seurat preference profile."
    )
    parser.add_argument("paths", nargs="+", help="Interaction log files/directories")
    parser.add_argument("--output", required=True, help="Output profile JSON path")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    events = valid_events(args.paths)
    try:
        document = build_preference_profile(events)
    except ValueError as error:
        parser.error(str(error))
    target = write_profile(document, args.output)
    source = document["source"]
    print(f"Preference profile: {target}")
    print(f"Events: {source['event_count']}")
    print(f"Sessions: {source['session_count']}")
    print(f"Preference examples: {source['preference_example_count']}")
    print(
        "Workspace groups: "
        f"{len(document['workspace_preferences']['groups'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
