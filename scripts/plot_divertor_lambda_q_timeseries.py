#!/usr/bin/env python3
"""Plot XGC divertor Eich lambda_q over heatdiag time."""

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
    parser.add_argument("--fit-window-mm", nargs=2, type=float, default=(-2.0, 20.0), metavar=("MIN", "MAX"))
    parser.add_argument("--smoothing-sigma-mm", type=float, default=0.0)
    parser.add_argument("--ylim", nargs=2, type=float, default=None, metavar=("MIN", "MAX"))
    parser.add_argument("--target", choices=("outer", "inner", "both"), default="both")
    parser.add_argument("--style", choices=("lines", "symbols", "both"), default="lines")
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
            compute_divertor_lambda_q_timeseries,
            plot_divertor_lambda_q_timeseries,
        )
    except (ImportError, ModuleNotFoundError) as exc:
        raise RuntimeError(
            f"Could not import the lambda_q routines from {analysis_path}: {exc}"
        ) from exc

    time_window = tuple(value*1.0e-3 for value in args.time_range_ms) if args.time_range_ms else None
    points = compute_divertor_lambda_q_timeseries(
        run_dir,
        include_sheath=args.include_sheath,
        step_range=tuple(args.step_range) if args.step_range else None,
        time_window=time_window,
        selected_frame_index=args.frame_index,
        psi_window=tuple(args.psi_window),
        fit_window_mm=tuple(args.fit_window_mm),
        smoothing_sigma_mm=max(0.0, args.smoothing_sigma_mm),
        show_outer=args.target in {"outer", "both"},
        show_inner=args.target in {"inner", "both"},
    )
    fig = plot_divertor_lambda_q_timeseries(
        points,
        ylim=tuple(args.ylim) if args.ylim else None,
        show_lines=args.style in {"lines", "both"},
        show_symbols=args.style in {"symbols", "both"},
    )

    out_dir = (args.out_dir or run_dir / "plots_all_steps").expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / "divertor_lambda_q_timeseries.png"
    try:
        fig.savefig(output, bbox_inches="tight")
    finally:
        plt.close(fig)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
