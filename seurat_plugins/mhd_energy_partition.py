"""MHD energy-partition diagnostic for scalar energy time series."""

from __future__ import annotations

import numpy as np

from ._mhd_energy import (
    COMPONENT_VARIABLES,
    ENERGY_VARIABLES,
    X_AXIS_CHOICES,
    has_duplicate_or_nonmonotonic_x,
    read_scalar_series,
    safe_fraction,
    supports_scalar_energy_timeseries,
    x_axis,
)


PLUGIN_ID = "mhd_energy_partition"
LABEL = "MHD energy partition"


def supports(meta):
    """Support scalar MHD energy variables with more than one ADIOS step."""
    return supports_scalar_energy_timeseries(meta, ENERGY_VARIABLES)


def options_schema(meta):
    """Return user-editable plotting options."""
    return [
        {
            "key": "x_axis",
            "type": "select",
            "label": "X axis",
            "choices": list(X_AXIS_CHOICES),
            "default": "time",
        },
        {
            "key": "denominator",
            "type": "select",
            "label": "Denominator",
            "choices": ["total_energy", "component_sum"],
            "default": "total_energy",
        },
    ]


def render(ctx):
    """Return internal, kinetic, and magnetic energy fractions over time."""
    helpers = ctx["helpers"]
    steps_count = int(ctx.get("steps_count", 1) or 1)
    if steps_count <= 1:
        raise ValueError("MHD energy partition requires more than one ADIOS step")

    options = dict(ctx.get("options", {}) or {})
    x_axis_name = str(options.get("x_axis", "time") or "time")
    x_values, x_label = x_axis(ctx, helpers, x_axis_name, steps_count)

    missing = []
    components = {}
    for name in COMPONENT_VARIABLES:
        try:
            components[name] = read_scalar_series(helpers, name, steps_count)
        except Exception:
            missing.append(name)
    if missing:
        raise ValueError(
            "MHD energy partition requires "
            + ", ".join(COMPONENT_VARIABLES)
            + "; missing "
            + ", ".join(missing)
        )

    component_sum = np.sum(
        np.vstack([components[name] for name in COMPONENT_VARIABLES]),
        axis=0,
    )
    denominator_choice = str(
        options.get("denominator", "total_energy") or "total_energy"
    )
    denominator_label = "total_energy"
    note_parts = [f"plugin: {PLUGIN_ID}"]
    if denominator_choice == "component_sum":
        denominator = component_sum
        denominator_label = "component sum"
    else:
        try:
            denominator = read_scalar_series(helpers, "total_energy", steps_count)
        except Exception:
            denominator = component_sum
            denominator_label = "component sum"
            note_parts.append("total_energy unavailable; using component sum")

    labels = {
        "internal_energy": "internal_energy",
        "kinetic_energy": "kinetic_energy",
        "magnetic_energy": "magnetic_energy",
    }
    series = []
    for name in COMPONENT_VARIABLES:
        series.append(
            {
                "x": x_values,
                "y": safe_fraction(components[name], denominator),
                "source_label": f"{labels[name]} / {denominator_label}",
                "source_key": f"{name}_fraction",
            }
        )

    note_parts.append(f"denominator: {denominator_label}")
    if x_label != "adios_step" and has_duplicate_or_nonmonotonic_x(x_values):
        note_parts.append(f"{x_label} axis has duplicate or non-monotonic values")

    plot = helpers.plot1d_payload(
        series,
        x_label=x_label,
        y_label="energy fraction",
    )
    return {
        "media_type": "plot1d",
        "display_title": "MHD energy partition",
        "plot": plot,
        "status": "ok",
        "note": "; ".join(note_parts),
    }
