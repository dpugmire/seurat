#!/usr/bin/env python3
"""Run ensembles of Orszag-Tang simulations with varying solver/parameters."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any


def to_cli_args(options: dict[str, Any]) -> list[str]:
    args: list[str] = []
    for key, value in options.items():
        if value is None:
            continue

        opt = f"--{key.replace('_', '-')}"

        if key == "save_initial":
            args.append("--save-initial" if bool(value) else "--no-save-initial")
            continue

        if isinstance(value, bool):
            if value:
                args.append(opt)
            continue

        args.extend([opt, str(value)])
    return args


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an Orszag-Tang ensemble")
    parser.add_argument("--config", required=True, help="Path to JSON ensemble config")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without running")
    parser.add_argument("--keep-going", action="store_true", help="Continue after failed members")
    parser.add_argument("--only", nargs="*", default=None, help="Run only selected case names")
    args = parser.parse_args()

    config_path = Path(args.config)
    with config_path.open("r", encoding="utf-8") as f:
        cfg = json.load(f)

    base_dir = config_path.resolve().parent

    binary_cfg = Path(cfg.get("binary", "./build/ot_mhd"))
    binary = (binary_cfg if binary_cfg.is_absolute() else (base_dir / binary_cfg)).resolve()
    mpi_launcher = str(cfg.get("mpi_launcher", "mpirun -n {ranks}"))
    output_cfg = Path(cfg.get("output_dir", "runs"))
    output_dir = (output_cfg if output_cfg.is_absolute() else (base_dir / output_cfg)).resolve()
    common = dict(cfg.get("common_args", {}))
    runs = list(cfg.get("runs", []))

    if not runs:
        print("No runs in config", file=sys.stderr)
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    selected = set(args.only) if args.only else None

    failures = 0
    executed = 0

    for run in runs:
        name = run.get("name")
        if not name:
            print("Skipping entry without 'name'", file=sys.stderr)
            continue

        if selected and name not in selected:
            continue

        ranks = int(run.get("ranks", cfg.get("default_ranks", 1)))
        run_output_cfg = Path(run.get("output", str(output_dir / f"{name}.bp")))
        run_output = (run_output_cfg if run_output_cfg.is_absolute() else (base_dir / run_output_cfg)).resolve()

        per_run = {k: v for k, v in run.items() if k not in {"name", "ranks", "output", "mpi_launcher"}}
        merged = dict(common)
        merged.update(per_run)
        merged["output"] = str(run_output)

        cmd = [str(binary)] + to_cli_args(merged)

        launcher_tmpl = str(run.get("mpi_launcher", mpi_launcher))
        if ranks > 1:
            launch_prefix = shlex.split(launcher_tmpl.format(ranks=ranks))
            cmd = launch_prefix + cmd

        executed += 1
        printable = " ".join(shlex.quote(part) for part in cmd)
        print(f"[{name}] {printable}")

        if args.dry_run:
            continue

        result = subprocess.run(cmd)
        if result.returncode != 0:
            failures += 1
            print(f"Run '{name}' failed with code {result.returncode}", file=sys.stderr)
            if not args.keep_going:
                return result.returncode

    if executed == 0:
        print("No runs selected", file=sys.stderr)
        return 1

    if failures:
        print(f"Finished with {failures} failed run(s)", file=sys.stderr)
        return 1

    print("Ensemble completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
