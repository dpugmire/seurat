#!/usr/bin/env python3
"""Plot a mapped XGC divertor particle or energy load from heatdiag data."""

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
    parser.add_argument("--view", choices=("time", "toroidal"), default="time")
    parser.add_argument("--channel", choices=("energy", "particle"), default="energy")
    parser.add_argument("--target", choices=("outer", "inner"), default="outer")
    parser.add_argument("--component", choices=("total", "ion", "electron"), default="total")
    parser.add_argument("--psi-window", nargs=2, type=float, default=(0.97, 1.12), metavar=("MIN", "MAX"))
    parser.add_argument("--delta-sep-range-mm", nargs=2, type=float, default=None, metavar=("MIN", "MAX"))
    parser.add_argument("--toroidal-range-deg", nargs=2, type=float, default=None, metavar=("MIN", "MAX"))
    parser.add_argument("--clim", nargs=2, type=float, default=None, metavar=("MIN", "MAX"))
    parser.add_argument("--contour-count", type=int, default=256)
    parser.add_argument("--cmap", default="seismic")
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
        from xgc_analysis.divertor_eich import compute_divertor_load_map, plot_divertor_load_map
    except (ImportError, ModuleNotFoundError) as exc:
        raise RuntimeError(
            f"Could not import the load-map routines from {analysis_path}: {exc}"
        ) from exc

    time_window = tuple(value*1.0e-3 for value in args.time_range_ms) if args.time_range_ms else None
    load_map = compute_divertor_load_map(
        run_dir,
        include_sheath=args.include_sheath,
        view=args.view,
        channel=args.channel,
        target=args.target,
        component=args.component,
        step_range=tuple(args.step_range) if args.step_range else None,
        time_window=time_window,
        selected_frame_index=args.frame_index,
        psi_window=tuple(args.psi_window),
    )
    if args.view == "time":
        y_range = tuple(args.time_range_ms) if args.time_range_ms else None
    else:
        y_range = tuple(args.toroidal_range_deg) if args.toroidal_range_deg else None
    fig = plot_divertor_load_map(
        load_map,
        xlim=tuple(args.delta_sep_range_mm) if args.delta_sep_range_mm else None,
        ylim=y_range,
        clim=tuple(args.clim) if args.clim else None,
        contour_count=max(2, args.contour_count),
        cmap=args.cmap,
    )

    out_dir = (args.out_dir or run_dir / "plots_all_steps").expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / f"divertor_load_map_{args.view}.png"
    try:
        fig.savefig(output, bbox_inches="tight")
    finally:
        plt.close(fig)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
