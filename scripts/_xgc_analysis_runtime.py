"""Runtime discovery shared by the standalone XGC analysis scripts."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys


def configure_xgc_analysis(requested: Path | None) -> Path:
    """Add the first checkout containing ``xgc_analysis`` to ``sys.path``."""
    candidates = []
    if requested is not None:
        candidates.append(requested)

    env_path = os.environ.get("XGC_ANALYSIS_PATH", "").strip()
    if env_path:
        candidates.append(Path(env_path))

    candidates.append(Path(__file__).resolve().parents[2] / "XGC-Analysis")

    checked = []
    for candidate in candidates:
        checkout = candidate.expanduser().resolve()
        if checkout in checked:
            continue
        checked.append(checkout)
        if not (checkout / "xgc_analysis").is_dir():
            continue
        checkout_text = str(checkout)
        if checkout_text not in sys.path:
            sys.path.insert(0, checkout_text)
        return checkout

    locations = ", ".join(str(path) for path in checked)
    raise RuntimeError(f"Could not locate an XGC-Analysis checkout. Checked: {locations}")


def require_analysis_modules() -> None:
    """Report missing runtime modules before importing XGC-Analysis."""
    required = ("adios2", "matplotlib", "numpy", "scipy", "xgc_analysis")
    missing = [name for name in required if importlib.util.find_spec(name) is None]
    if missing:
        names = ", ".join(missing)
        raise RuntimeError(f"Missing Python modules in {sys.executable}: {names}")
