"""MHD energy-conservation diagnostic for scalar energy time series."""

from __future__ import annotations

import numpy as np

from ._mhd_energy import (
    COMPONENT_VARIABLES,
    ENERGY_VARIABLES,
    X_AXIS_CHOICES,
    has_duplicate_or_nonmonotonic_x,
    read_scalar_series,
    relative_change_to_initial,
    safe_fraction,
    supports_scalar_energy_timeseries,
    x_axis,
)


PLUGIN_ID = "mhd_energy_conservation"
LABEL = "MHD energy conservation"


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
            "key": "show_component_residual",
            "type": "bool",
            "label": "Show component residual",
            "default": True,
        },
    ]


def render(ctx):
    """Return a relative total-energy drift plot."""
    helpers = ctx["helpers"]
    steps_count = int(ctx.get("steps_count", 1) or 1)
    if steps_count <= 1:
        raise ValueError("MHD energy conservation requires more than one ADIOS step")

    options = dict(ctx.get("options", {}) or {})
    x_axis_name = str(options.get("x_axis", "time") or "time")
    x_values, x_label = x_axis(ctx, helpers, x_axis_name, steps_count)

    total = read_scalar_series(helpers, "total_energy", steps_count)
    relative_total = relative_change_to_initial(total, "total_energy")
    series = [
        {
            "x": x_values,
            "y": relative_total,
            "source_label": "(total_energy - total_energy[0]) / |total_energy[0]|",
            "source_key": "relative_total_energy_change",
        }
    ]

    note_parts = [f"plugin: {PLUGIN_ID}", "relative to initial total_energy"]
    if bool(options.get("show_component_residual", True)):
        missing = []
        components = []
        for name in COMPONENT_VARIABLES:
            try:
                components.append(read_scalar_series(helpers, name, steps_count))
            except Exception:
                missing.append(name)
        if missing:
            note_parts.append(
                "component residual unavailable; missing " + ", ".join(missing)
            )
        else:
            residual = total - np.sum(np.vstack(components), axis=0)
            relative_residual = safe_fraction(residual, np.abs(total))
            series.append(
                {
                    "x": x_values,
                    "y": relative_residual,
                    "source_label": (
                        "(total_energy - internal_energy - kinetic_energy - "
                        "magnetic_energy) / |total_energy|"
                    ),
                    "source_key": "component_energy_residual",
                }
            )

    if x_label != "adios_step" and has_duplicate_or_nonmonotonic_x(x_values):
        note_parts.append(f"{x_label} axis has duplicate or non-monotonic values")

    plot = helpers.plot1d_payload(
        series,
        x_label=x_label,
        y_label="relative energy error",
    )
    return {
        "media_type": "plot1d",
        "display_title": "MHD energy conservation",
        "plot": plot,
        "status": "ok",
        "note": "; ".join(note_parts),
    }
