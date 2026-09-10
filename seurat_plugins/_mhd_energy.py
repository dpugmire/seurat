"""Shared helpers for MHD energy plotting plugins."""

from __future__ import annotations

import numpy as np


COMPONENT_VARIABLES = ("internal_energy", "kinetic_energy", "magnetic_energy")
ENERGY_VARIABLES = ("total_energy", *COMPONENT_VARIABLES)
X_AXIS_CHOICES = ("time", "step", "adios_step")


def variable_basename(meta):
    for key in ("variable_name", "variable_id", "variable_path"):
        text = str(meta.get(key, "") or "").strip("/")
        if text:
            return text.split("/")[-1]
    return ""


def supports_scalar_energy_timeseries(meta, names=ENERGY_VARIABLES):
    try:
        ndims = int(meta.get("ndims", -1))
        steps_count = int(meta.get("steps_count", 1) or 1)
    except Exception:
        return False
    return ndims == 0 and steps_count > 1 and variable_basename(meta) in set(names)


def read_scalar_series(helpers, name, steps_count):
    raw = np.asarray(
        helpers.read_source_variable(name, step_selection=(0, steps_count))
    )
    if np.iscomplexobj(raw):
        raise ValueError(f"Complex-valued {name} is not supported")

    data = np.asarray(raw, dtype=float)
    flat = data.reshape(-1)
    if flat.size == steps_count:
        return flat
    if flat.size % steps_count == 0:
        reshaped = flat.reshape(steps_count, flat.size // steps_count)
        if reshaped.shape[1] == 1:
            return reshaped[:, 0]
    raise ValueError(
        f"Expected scalar {name} to have one value per ADIOS step; "
        f"got shape {data.shape} for {steps_count} steps"
    )


def x_axis(ctx, helpers, x_axis_name, steps_count):
    if x_axis_name not in X_AXIS_CHOICES:
        x_axis_name = "adios_step"
    if x_axis_name == "adios_step":
        return np.arange(steps_count, dtype=float), "adios_step"

    try:
        values = helpers.read_source_variable(
            x_axis_name,
            step_selection=(0, steps_count),
        )
    except Exception:
        return np.arange(steps_count, dtype=float), "adios_step"

    x = np.asarray(values, dtype=float).reshape(-1)
    if x.size != steps_count or not np.all(np.isfinite(x)):
        return np.arange(steps_count, dtype=float), "adios_step"
    return x, x_axis_name


def relative_change_to_initial(values, label):
    y = np.asarray(values, dtype=float).reshape(-1)
    if y.size <= 0 or not np.isfinite(y[0]):
        raise ValueError(
            f"Cannot compute relative change; initial {label} is not finite"
        )
    baseline = float(y[0])
    if baseline == 0.0:
        raise ValueError(f"Cannot compute relative change; initial {label} is zero")
    return (y - baseline) / abs(baseline)


def safe_fraction(numerator, denominator):
    num = np.asarray(numerator, dtype=float)
    den = np.asarray(denominator, dtype=float)
    out = np.full_like(num, np.nan, dtype=float)
    mask = np.isfinite(num) & np.isfinite(den) & (den != 0.0)
    return np.divide(num, den, out=out, where=mask)


def has_duplicate_or_nonmonotonic_x(values):
    x = np.asarray(values, dtype=float).reshape(-1)
    if x.size <= 1:
        return False
    return np.unique(x).size != x.size or bool(np.any(np.diff(x) <= 0))
