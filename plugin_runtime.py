"""Runtime support for Seurat Python plotting plugins."""

from __future__ import annotations

import importlib
import importlib.util
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from adios2 import FileReader


PLUGIN_VIS_PREFIX = "plugin:"
PERSONAL_PLUGIN_ENV = "SEURAT_PLUGIN_PATH"
DEFAULT_PERSONAL_PLUGIN_DIR = Path("~/.seurat/plugins")


@dataclass(frozen=True)
class PluginInfo:
    plugin_id: str
    label: str
    module_name: str
    scope: str = "variable"


_BUILTIN_PLUGIN_MODULES = (
    "seurat_plugins.profile_timeseries",
    "seurat_plugins.paired_species_profile",
    "seurat_plugins.radial_flux_corrected",
    "seurat_plugins.divertor_eich_profile",
    "seurat_plugins.divertor_lambda_q_timeseries",
    "seurat_plugins.divertor_load_map",
    "seurat_plugins.divertor_target_totals_timeseries",
)


def plugin_visualization_name(plugin_id: str) -> str:
    return f"{PLUGIN_VIS_PREFIX}{str(plugin_id or '').strip()}"


def is_plugin_visualization(name: str) -> bool:
    return str(name or "").strip().startswith(PLUGIN_VIS_PREFIX)


def plugin_id_from_visualization(name: str) -> str:
    text = str(name or "").strip()
    if not is_plugin_visualization(text):
        return ""
    return text[len(PLUGIN_VIS_PREFIX) :].strip()


def discover_plugins() -> List[PluginInfo]:
    plugin_ids: set[str] = set()
    plugins: List[PluginInfo] = []
    for module_name in _BUILTIN_PLUGIN_MODULES:
        mod = importlib.import_module(module_name)
        info = _plugin_info_from_module(mod, module_name)
        if info is None:
            continue
        plugins.append(info)
        plugin_ids.add(info.plugin_id)

    for mod, module_name in _load_personal_plugin_modules():
        info = _plugin_info_from_module(mod, module_name)
        if info is None:
            continue
        if info.plugin_id in plugin_ids:
            print(f"Skipping personal Seurat plugin with duplicate PLUGIN_ID: {info.plugin_id}", file=sys.stderr)
            continue
        plugins.append(info)
        plugin_ids.add(info.plugin_id)
    return plugins


def plugin_info(plugin_id: str) -> Optional[PluginInfo]:
    target = str(plugin_id or "").strip()
    return next((info for info in discover_plugins() if info.plugin_id == target), None)


def load_plugin(plugin_id: str):
    info = plugin_info(plugin_id)
    if info is None:
        raise ValueError(f"Unknown plugin: {plugin_id}")
    return importlib.import_module(info.module_name)


def _plugin_info_from_module(mod: Any, module_name: str) -> Optional[PluginInfo]:
    plugin_id = str(getattr(mod, "PLUGIN_ID", "") or "").strip()
    if not plugin_id:
        return None
    label = str(getattr(mod, "LABEL", "") or plugin_id)
    scope = str(getattr(mod, "PLUGIN_SCOPE", "variable") or "variable").strip().lower()
    if scope not in {"variable", "source"}:
        scope = "variable"
    return PluginInfo(plugin_id=plugin_id, label=label, module_name=module_name, scope=scope)


def _personal_plugin_dirs() -> List[Path]:
    raw = os.environ.get(PERSONAL_PLUGIN_ENV, "")
    dirs: List[Path] = []
    candidates = [str(DEFAULT_PERSONAL_PLUGIN_DIR)]
    if raw.strip():
        candidates.extend(item.strip() for item in raw.split(os.pathsep))

    for item in candidates:
        if not item:
            continue
        path = Path(item).expanduser()
        if path not in dirs:
            dirs.append(path)
    return dirs


def _load_personal_plugin_modules() -> List[Tuple[Any, str]]:
    modules: List[Tuple[Any, str]] = []
    for plugin_dir in _personal_plugin_dirs():
        if not plugin_dir.is_dir():
            continue
        for path in sorted(plugin_dir.glob("*.py")):
            if path.name.startswith("_"):
                continue
            module_name = _personal_plugin_module_name(path)
            try:
                mod = _load_module_from_path(module_name, path)
            except Exception as exc:
                print(f"Skipping personal Seurat plugin {path}: {type(exc).__name__}: {exc}", file=sys.stderr)
                continue
            modules.append((mod, module_name))
    return modules


def _personal_plugin_module_name(path: Path) -> str:
    resolved = path.expanduser().resolve()
    token = str(abs(hash(str(resolved))))
    stem = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in resolved.stem)
    return f"_seurat_personal_plugin_{stem}_{token}"


def _load_module_from_path(module_name: str, path: Path):
    cached = sys.modules.get(module_name)
    if cached is not None:
        return cached

    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module spec for {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return mod


def plugin_scope(plugin_id: str) -> str:
    info = plugin_info(plugin_id)
    return info.scope if info is not None else ""


def normalize_options_schema(raw: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key", "") or "").strip()
        label = str(item.get("label", "") or "").strip()
        option_type = str(item.get("type", "text") or "text").strip().lower()
        if not key or not label:
            continue
        if option_type not in {"text", "number", "bool", "select"}:
            option_type = "text"
        normalized: Dict[str, Any] = {"key": key, "type": option_type, "label": label}
        if option_type == "bool":
            normalized["default"] = bool(item.get("default", False))
        else:
            normalized["default"] = str(item.get("default", "") or "")
        if option_type == "select":
            choices = [str(choice) for choice in item.get("choices", []) or [] if str(choice)]
            normalized["choices"] = choices
            if choices and normalized["default"] not in choices:
                normalized["default"] = choices[0]
        out.append(normalized)
    return out


def default_options(schema: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    options: Dict[str, Any] = {}
    for item in schema:
        key = str(item.get("key", "") or "")
        if not key:
            continue
        if str(item.get("type", "") or "") == "bool":
            options[key] = bool(item.get("default", False))
        else:
            options[key] = str(item.get("default", "") or "")
    return options


def normalize_plugin_options(
    schema: Sequence[Dict[str, Any]],
    values: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    raw_values = values if isinstance(values, dict) else {}
    options = default_options(schema)
    for item in schema:
        key = str(item.get("key", "") or "")
        if not key or key not in raw_values:
            continue
        option_type = str(item.get("type", "") or "")
        raw = raw_values.get(key)
        if option_type == "bool":
            options[key] = bool(raw)
        elif option_type == "number":
            options[key] = str(raw).strip()
        elif option_type == "select":
            value = str(raw or "").strip()
            choices = [str(choice) for choice in item.get("choices", []) or []]
            options[key] = value if not choices or value in choices else str(item.get("default", "") or "")
        else:
            options[key] = str(raw or "").strip()
    return options


def metadata_shape(metadata: Any) -> List[int]:
    if not isinstance(metadata, dict):
        return []
    raw_shape = metadata.get("Shape", metadata.get("shape", None))
    if raw_shape is None:
        return []
    text = str(raw_shape).strip()
    if not text:
        return []
    cleaned = text
    for ch in "[](){}":
        cleaned = cleaned.replace(ch, "")
    parts = [part.strip() for part in cleaned.replace("x", ",").split(",") if part.strip()]
    if not parts:
        parts = [part.strip() for part in cleaned.split() if part.strip()]
    dims: List[int] = []
    for part in parts:
        try:
            value = int(float(part))
        except Exception:
            continue
        if value > 0:
            dims.append(value)
    return dims


def metadata_ndims(metadata: Any) -> Optional[int]:
    if not isinstance(metadata, dict):
        return None
    single_value = metadata.get("SingleValue", None)
    if isinstance(single_value, bool) and single_value:
        return 0
    if isinstance(single_value, str) and single_value.strip().lower() in {"true", "1", "yes"}:
        return 0
    shape = metadata_shape(metadata)
    if not shape:
        return None
    if len(shape) == 1 and shape[0] <= 1:
        return 0
    return len(shape)


def metadata_steps_count(metadata: Any) -> int:
    if not isinstance(metadata, dict):
        return 1
    for key in ("AvailableStepsCount", "Steps", "steps"):
        raw = metadata.get(key, None)
        try:
            count = int(float(str(raw).strip()))
        except Exception:
            continue
        if count > 0:
            return count
    return 1


def build_plugin_meta(candidate: Dict[str, Any]) -> Dict[str, Any]:
    metadata = candidate.get("metadata", {}) or {}
    return {
        "variable_id": str(candidate.get("variable_id", "") or ""),
        "variable_name": str(candidate.get("variable_name", "") or candidate.get("variable_id", "") or ""),
        "variable_path": str(candidate.get("variable_path", "") or ""),
        "source_dataset": str((candidate.get("source_fields", {}) or {}).get("source_dataset", "") or ""),
        "source_fields": dict(candidate.get("source_fields", {}) or {}),
        "source_variables": list(candidate.get("source_variables", []) or []),
        "metadata": metadata,
        "ndims": metadata_ndims(metadata),
        "steps_count": metadata_steps_count(metadata),
        "shape": metadata_shape(metadata),
        "min": candidate.get("min", None),
        "max": candidate.get("max", None),
    }


def supported_plugin_visualizations(meta: Dict[str, Any]) -> List[str]:
    names: List[str] = []
    for info in discover_plugins():
        if info.scope != "variable":
            continue
        mod = importlib.import_module(info.module_name)
        supports = getattr(mod, "supports", None)
        try:
            supported = bool(supports(meta)) if callable(supports) else True
        except Exception:
            supported = False
        if supported:
            names.append(plugin_visualization_name(info.plugin_id))
    return names


def supported_source_plugins(meta: Dict[str, Any]) -> List[PluginInfo]:
    plugins: List[PluginInfo] = []
    for info in discover_plugins():
        if info.scope != "source":
            continue
        mod = importlib.import_module(info.module_name)
        supports = getattr(mod, "supports_context", None)
        if not callable(supports):
            supports = getattr(mod, "supports", None)
        try:
            supported = bool(supports(meta)) if callable(supports) else True
        except Exception:
            supported = False
        if supported:
            plugins.append(info)
    return plugins


def plugin_options_schema(plugin_id: str, meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    mod = load_plugin(plugin_id)
    schema_fn = getattr(mod, "options_schema", None)
    if not callable(schema_fn):
        return []
    return normalize_options_schema(schema_fn(meta))


class PluginHelpers:
    def __init__(self, campaign_path: str, source_dataset: str):
        self.campaign_path = str(campaign_path or "")
        self.source_dataset = str(source_dataset or "").strip("/")

    def read_variable(self, variable_path: str, step_selection: Optional[Tuple[int, int]] = None):
        kwargs = {"step_selection": list(step_selection)} if step_selection else {}
        with FileReader(self.campaign_path) as fr:
            return fr.read(str(variable_path or "").strip("/"), **kwargs)

    def read_source_variable(self, name: str, step_selection: Optional[Tuple[int, int]] = None):
        key = str(name or "").strip("/")
        variable_path = f"{self.source_dataset}/{key}" if self.source_dataset and not key.startswith(self.source_dataset + "/") else key
        return self.read_variable(variable_path, step_selection=step_selection)

    def plot1d_payload(self, series_values: List[Dict[str, Any]], x_label: str, y_label: str) -> Dict[str, Any]:
        return plot1d_payload(series_values, x_label, y_label)


def render_plugin_tile(
    campaign_path: str,
    plugin_id: str,
    candidate: Dict[str, Any],
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    mod = load_plugin(plugin_id)
    meta = build_plugin_meta(candidate)
    supports = getattr(mod, "supports", None)
    if callable(supports) and not bool(supports(meta)):
        raise ValueError(f"Plugin {plugin_id} does not support this variable/source")

    schema = plugin_options_schema(plugin_id, meta)
    normalized_options = normalize_plugin_options(schema, options)
    source_fields = dict(candidate.get("source_fields", {}) or {})
    helpers = PluginHelpers(campaign_path, str(source_fields.get("source_dataset", "") or ""))
    ctx = {
        **meta,
        "campaign_path": campaign_path,
        "plugin_id": plugin_id,
        "options": normalized_options,
        "helpers": helpers,
    }
    render = getattr(mod, "render", None)
    if not callable(render):
        raise ValueError(f"Plugin {plugin_id} has no render(ctx)")

    tile = render(ctx)
    if not isinstance(tile, dict):
        raise ValueError(f"Plugin {plugin_id} returned {type(tile).__name__}, expected dict")
    tile = dict(tile)
    tile["plugin_id"] = plugin_id
    tile["plugin_label"] = str(getattr(mod, "LABEL", "") or plugin_id)
    tile["plugin_options_schema"] = schema
    tile["plugin_options"] = normalized_options
    tile["visualization_name"] = plugin_visualization_name(plugin_id)
    tile["selected_visualization"] = plugin_visualization_name(plugin_id)
    tile["visualization_options"] = [plugin_visualization_name(plugin_id)]
    return tile


def render_source_plugin_tile(
    campaign_path: str,
    plugin_id: str,
    meta: Dict[str, Any],
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    mod = load_plugin(plugin_id)
    if plugin_scope(plugin_id) != "source":
        raise ValueError(f"Plugin {plugin_id} is not a source plugin")

    supports = getattr(mod, "supports_context", None)
    if not callable(supports):
        supports = getattr(mod, "supports", None)
    if callable(supports) and not bool(supports(meta)):
        raise ValueError(f"Plugin {plugin_id} does not support this source")

    schema = plugin_options_schema(plugin_id, meta)
    normalized_options = normalize_plugin_options(schema, options)
    source_fields = dict(meta.get("source_fields", {}) or {})
    helpers = PluginHelpers(campaign_path, str(source_fields.get("source_dataset", "") or ""))
    ctx = {
        **dict(meta or {}),
        "campaign_path": campaign_path,
        "plugin_id": plugin_id,
        "options": normalized_options,
        "helpers": helpers,
    }

    render = getattr(mod, "render", None)
    if not callable(render):
        raise ValueError(f"Plugin {plugin_id} has no render(ctx)")

    tile = render(ctx)
    if not isinstance(tile, dict):
        raise ValueError(f"Plugin {plugin_id} returned {type(tile).__name__}, expected dict")
    tile = dict(tile)
    tile["plugin_id"] = plugin_id
    tile["plugin_label"] = str(getattr(mod, "LABEL", "") or plugin_id)
    tile["plugin_options_schema"] = schema
    tile["plugin_options"] = normalized_options
    tile["visualization_name"] = plugin_visualization_name(plugin_id)
    tile["selected_visualization"] = plugin_visualization_name(plugin_id)
    tile["visualization_options"] = [plugin_visualization_name(plugin_id)]
    tile["plugin_scope"] = "source"
    return tile


def plot1d_payload(series_values: List[Dict[str, Any]], x_label: str, y_label: str) -> Dict[str, Any]:
    colors = (
        "#1565c0",
        "#c62828",
        "#2e7d32",
        "#ef6c00",
        "#6a1b9a",
        "#00838f",
        "#ad1457",
        "#5d4037",
    )
    series: List[Dict[str, Any]] = []
    all_x: List[np.ndarray] = []
    all_y: List[np.ndarray] = []

    for item in series_values:
        x, y = _clean_plot_series(item.get("x", []), item.get("y", []))
        if x.size <= 0:
            continue
        all_x.append(x)
        all_y.append(y)
        series.append(
            {
                "x": [float(v) for v in x],
                "y": [float(v) for v in y],
                "source_label": str(item.get("source_label", "") or ""),
                "source_key": str(item.get("source_key", "") or ""),
                "color": colors[len(series) % len(colors)],
            }
        )

    if not series:
        raise ValueError("No finite values available for plot")

    x_values = np.concatenate(all_x)
    y_values = np.concatenate(all_y)
    xmin = float(np.min(x_values))
    xmax = float(np.max(x_values))
    ymin = float(np.min(y_values))
    ymax = float(np.max(y_values))

    x_axis_min, x_axis_max = _axis_limits(xmin, xmax)
    y_axis_min, y_axis_max = _axis_limits(ymin, ymax)
    return {
        "x_label": str(x_label or "x"),
        "y_label": str(y_label or ""),
        "x_min": x_axis_min,
        "x_max": x_axis_max,
        "y_min": y_axis_min,
        "y_max": y_axis_max,
        "data_x_min": xmin,
        "data_x_max": xmax,
        "data_y_min": ymin,
        "data_y_max": ymax,
        "series": series,
    }


def _clean_plot_series(x_values: Any, y_values: Any) -> Tuple[np.ndarray, np.ndarray]:
    x = np.asarray(x_values, dtype=float).reshape(-1)
    y = np.asarray(y_values, dtype=float).reshape(-1)
    n = min(int(x.size), int(y.size))
    if n <= 0:
        return np.asarray([], dtype=float), np.asarray([], dtype=float)
    x = x[:n]
    y = y[:n]
    mask = np.isfinite(x) & np.isfinite(y)
    return x[mask], y[mask]


def _axis_limits(axis_min: float, axis_max: float) -> Tuple[float, float]:
    if math.isclose(axis_min, axis_max):
        pad = abs(axis_min) * 0.05 if axis_min else 1.0
        return axis_min - pad, axis_max + pad
    pad = (axis_max - axis_min) * 0.06
    return axis_min - pad, axis_max + pad
