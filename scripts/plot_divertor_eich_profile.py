#!/usr/bin/env python3
"""Plot an XGC divertor Eich profile from ``xgc.heatdiag2.bp``."""

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
        help="Output directory. Defaults to <run_dir>/plots.",
    )
    parser.add_argument(
        "--xgc-analysis-path",
        type=Path,
        default=None,
        help="XGC-Analysis checkout; overrides XGC_ANALYSIS_PATH.",
    )
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--frame-index", type=int, default=None, help="Heatdiag frame index.")
    selection.add_argument(
        "--time-window-ms",
        nargs=2,
        type=float,
        metavar=("MIN", "MAX"),
        help="Average intervals overlapping this time window, in ms.",
    )
    parser.add_argument("--psi-window", nargs=2, type=float, default=(0.97, 1.12), metavar=("MIN", "MAX"))
    parser.add_argument("--fit-window-mm", nargs=2, type=float, default=(-2.0, 20.0), metavar=("MIN", "MAX"))
    parser.add_argument("--smoothing-sigma-mm", type=float, default=0.0)
    parser.add_argument("--xlim", nargs=2, type=float, default=None, metavar=("MIN", "MAX"))
    parser.add_argument("--ylim", nargs=2, type=float, default=None, metavar=("MIN", "MAX"))
    parser.add_argument("--target", choices=("outer", "inner", "both"), default="both")
    parser.add_argument("--channel", choices=("particle", "energy", "both"), default="both")
    parser.add_argument(
        "--components",
        nargs="+",
        choices=("ion", "electron", "total"),
        default=("ion", "electron", "total"),
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
        from xgc_analysis.divertor_eich import compute_divertor_eich_profiles, plot_divertor_eich_profiles
    except (ImportError, ModuleNotFoundError) as exc:
        raise RuntimeError(
            f"Could not import the Eich-profile routines from {analysis_path}: {exc}"
        ) from exc

    components = set(args.components)
    profiles = compute_divertor_eich_profiles(
        run_dir,
        include_sheath=args.include_sheath,
        time_window=(tuple(value*1.0e-3 for value in args.time_window_ms) if args.time_window_ms else None),
        selected_frame_index=args.frame_index,
        psi_window=tuple(args.psi_window),
        fit_window_mm=tuple(args.fit_window_mm),
        smoothing_sigma_mm=max(0.0, args.smoothing_sigma_mm),
        show_outer=args.target in {"outer", "both"},
        show_inner=args.target in {"inner", "both"},
    )
    fig = plot_divertor_eich_profiles(
        profiles,
        show_particle=args.channel in {"particle", "both"},
        show_energy=args.channel in {"energy", "both"},
        show_ions="ion" in components,
        show_electrons="electron" in components,
        show_total="total" in components,
        xlim=tuple(args.xlim) if args.xlim else None,
        ylim=tuple(args.ylim) if args.ylim else None,
    )

    out_dir = (args.out_dir or run_dir / "plots").expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / "divertor_eich_profile.png"
    try:
        fig.savefig(output, bbox_inches="tight")
    finally:
        plt.close(fig)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
