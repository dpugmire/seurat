#!/usr/bin/env python3
"""Plot XGC divertor target particle and power totals over heatdiag time."""

from __future__ import annotations

import argparse
from pathlib import Path

from _xgc_analysis_runtime import configure_xgc_analysis, require_analysis_modules


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path, help="XGC run directory containing xgc.heatdiag2.bp.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory. Defaults to <run_dir>/plots_all_steps.",
    )
    parser.add_argument("--xgc-analysis-path", type=Path, default=None)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--step-range", nargs=2, type=float, metavar=("MIN", "MAX"))
    selection.add_argument("--time-range-ms", nargs=2, type=float, metavar=("MIN", "MAX"))
    selection.add_argument("--frame-index", type=int, default=None)
    parser.add_argument("--psi-window", nargs=2, type=float, default=(0.97, 1.12), metavar=("MIN", "MAX"))
    parser.add_argument("--xlim-ms", nargs=2, type=float, default=None, metavar=("MIN", "MAX"))
    parser.add_argument("--particle-ylim", nargs=2, type=float, default=None, metavar=("MIN", "MAX"))
    parser.add_argument("--power-ylim-mw", nargs=2, type=float, default=None, metavar=("MIN", "MAX"))
    parser.add_argument("--channel", choices=("particle", "power", "both"), default="both")
    parser.add_argument(
        "--traces",
        nargs="+",
        choices=("outer", "inner", "total", "control"),
        default=("outer", "inner", "total", "control"),
    )
    parser.add_argument(
        "--components",
        nargs="+",
        choices=("ion", "electron", "target-total"),
        default=("ion", "electron", "target-total"),
    )
    parser.add_argument("--include-sheath", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = args.run_dir.expanduser().resolve()
    if not (run_dir / "xgc.heatdiag2.bp").exists():
        raise FileNotFoundError(f"Missing {run_dir / 'xgc.heatdiag2.bp'}")

    analysis_path = configure_xgc_analysis(args.xgc_analysis_path)
    require_analysis_modules()
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    try:
        from xgc_analysis.divertor_eich import (
            compute_divertor_target_totals_timeseries,
            plot_divertor_target_totals_timeseries,
        )
    except (ImportError, ModuleNotFoundError) as exc:
        raise RuntimeError(
            f"Could not import the target-total routines from {analysis_path}: {exc}"
        ) from exc

    traces = set(args.traces)
    components = set(args.components)
    time_window = tuple(value*1.0e-3 for value in args.time_range_ms) if args.time_range_ms else None
    points = compute_divertor_target_totals_timeseries(
        run_dir,
        include_sheath=args.include_sheath,
        step_range=tuple(args.step_range) if args.step_range else None,
        time_window=time_window,
        selected_frame_index=args.frame_index,
        psi_window=tuple(args.psi_window),
        show_outer="outer" in traces,
        show_inner="inner" in traces,
        show_total="total" in traces,
        show_wall="control" in traces,
    )
    fig = plot_divertor_target_totals_timeseries(
        points,
        show_particle=args.channel in {"particle", "both"},
        show_power=args.channel in {"power", "both"},
        show_outer="outer" in traces,
        show_inner="inner" in traces,
        show_total="total" in traces,
        show_control="control" in traces,
        show_ions="ion" in components,
        show_electrons="electron" in components,
        show_target_total="target-total" in components,
        xlim_ms=tuple(args.xlim_ms) if args.xlim_ms else None,
        particle_ylim=tuple(args.particle_ylim) if args.particle_ylim else None,
        power_ylim_mw=tuple(args.power_ylim_mw) if args.power_ylim_mw else None,
    )

    out_dir = (args.out_dir or run_dir / "plots_all_steps").expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / "divertor_target_totals_timeseries.png"
    try:
        fig.savefig(output, bbox_inches="tight")
    finally:
        plt.close(fig)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
