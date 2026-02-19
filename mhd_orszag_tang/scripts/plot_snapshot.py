#!/usr/bin/env python3
"""Plot one time-step from an ADIOS2 BP file produced by ot_mhd."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


try:
    import adios2
except ImportError as exc:
    raise SystemExit("This script requires the Python package 'adios2'.") from exc


def read_var(reader, name: str, step: int) -> np.ndarray:
    try:
        data = reader.read(name, step_selection=[step, 1])
    except TypeError:
        data = reader.read(name, start=[], count=[], step_selection=[step, 1])
    return np.asarray(data)


def main() -> int:
    parser = argparse.ArgumentParser(description="Plot Orszag-Tang fields from ADIOS2 BP")
    parser.add_argument("--file", required=True, help="Path to .bp output")
    parser.add_argument("--step", type=int, default=-1, help="Step index (default: last)")
    parser.add_argument("--out", default="snapshot.png", help="Output PNG path")
    args = parser.parse_args()

    bp_path = Path(args.file)
    if not bp_path.exists():
        raise SystemExit(f"File not found: {bp_path}")

    with adios2.open(str(bp_path), "r") as reader:
        try:
            nsteps = int(reader.steps())
        except AttributeError:
            nsteps = int(reader.num_steps())

        if nsteps <= 0:
            raise SystemExit("No steps found in ADIOS file")

        step = args.step if args.step >= 0 else (nsteps - 1)
        if step < 0 or step >= nsteps:
            raise SystemExit(f"Invalid step {step}; available range is [0, {nsteps - 1}]")

        rho = read_var(reader, "rho", step)
        pressure = read_var(reader, "pressure", step)
        current_z = read_var(reader, "current_z", step)
        speed = read_var(reader, "speed", step)

    fig, axes = plt.subplots(2, 2, figsize=(10, 8), constrained_layout=True)
    panels = [
        (rho, "Density", "viridis"),
        (pressure, "Pressure", "magma"),
        (current_z, "Current density Jz", "RdBu_r"),
        (speed, "Speed |v|", "plasma"),
    ]

    for ax, (field, title, cmap) in zip(axes.flat, panels):
        im = ax.imshow(field, origin="lower", cmap=cmap, aspect="equal")
        ax.set_title(title)
        ax.set_xticks([])
        ax.set_yticks([])
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    fig.suptitle(f"{bp_path.name} step={step}")
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=170)
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
