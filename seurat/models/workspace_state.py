"""Versioned serialization for portable Seurat workspace state."""

import json
import re
from pathlib import Path
from typing import Any, Dict


WORKSPACE_FORMAT = "seurat-workspace"
WORKSPACE_VERSION = 1

_CELL_FIELDS = (
    "variable_id",
    "variable_name",
    "visualization_name",
    "selected_visualization",
    "source_id",
    "_source_key",
    "_source_keys",
    "_source_fields_list",
    "source_dataset",
    "schema_name",
    "schema_file_group",
    "schema_role",
    "schema_mode",
    "producer",
    "casename",
    "file",
    "variable_path",
    "variable_location",
    "metadata",
    "min",
    "max",
    "plot_settings",
    "plugin_id",
    "plugin_label",
    "plugin_scope",
    "plugin_options",
    "scalar_field_settings",
    "grid_row",
    "grid_col",
    "row_span",
    "col_span",
    "grid_hidden",
)


class WorkspaceStateError(ValueError):
    """Raised when a workspace state document cannot be saved or loaded."""


def _state_value(state, name: str, default: Any) -> Any:
    return getattr(state, name, default)


def _json_copy(value: Any, description: str) -> Any:
    try:
        encoded = json.dumps(value, allow_nan=False)
        return json.loads(encoded)
    except (TypeError, ValueError) as e:
        raise WorkspaceStateError(
            f"{description} is not JSON serializable: {e}"
        ) from e


def _invalid_json_constant(constant: str):
    raise ValueError(f"Invalid JSON number {constant}")


def _cell_state(cell: Dict[str, Any], index: int) -> Dict[str, Any]:
    return {
        field: _json_copy(cell[field], f"Grid cell {index + 1} field {field}")
        for field in _CELL_FIELDS
        if field in cell
    }


def default_workspace_filename(campaign_path: str) -> str:
    name = Path(str(campaign_path or "")).name
    stem = Path(name).stem if name else "seurat"
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-")
    return f"{safe_stem or 'seurat'}.json"


def workspace_document(state, campaign_path: str) -> Dict[str, Any]:
    """Return the durable, semantic subset of the current Trame state."""

    raw_cells = list(_state_value(state, "gridCells", []) or [])
    cells = [
        _cell_state(cell if isinstance(cell, dict) else {}, index)
        for index, cell in enumerate(raw_cells)
    ]
    campaign_name = Path(str(campaign_path or "")).name
    if not campaign_name:
        raise WorkspaceStateError("Cannot save state without a campaign name")

    return {
        "format": WORKSPACE_FORMAT,
        "version": WORKSPACE_VERSION,
        "campaign": {
            "name": campaign_name,
        },
        "state": {
            "catalog": {
                "variable_pane_view": str(
                    _state_value(state, "variablePaneView", "variables")
                    or "variables"
                ),
                "variable_group_collapsed_by_view": _json_copy(
                    _state_value(
                        state,
                        "variableGroupCollapsedByView",
                        {"variables": {}, "files": {}},
                    ),
                    "Variable group state",
                ),
                "show_only_visualized_variables": bool(
                    _state_value(state, "showOnlyVisualizedVars", False)
                ),
                "selected_variable": str(
                    _state_value(state, "selectedVar", "") or ""
                ),
                "query_text": str(_state_value(state, "queryText", "") or ""),
            },
            "grid": {
                "rows": _state_value(state, "gridRows", 3),
                "columns": _state_value(state, "gridCols", 3),
                "layout_mode": str(
                    _state_value(state, "gridLayoutMode", "uniform")
                    or "uniform"
                ),
                "sizing_mode": str(
                    _state_value(state, "gridSizingMode", "static") or "static"
                ),
                "cell_size": _state_value(state, "gridCellSize", 300),
                "fit_minimum_cell_size": _state_value(
                    state, "gridFitMinCellSize", 180
                ),
                "column_sizes": _json_copy(
                    _state_value(state, "gridColumnSizes", []),
                    "Grid column sizes",
                ),
                "row_sizes": _json_copy(
                    _state_value(state, "gridRowSizes", []),
                    "Grid row sizes",
                ),
                "column_weights": _json_copy(
                    _state_value(state, "gridColumnWeights", []),
                    "Grid column weights",
                ),
                "row_weights": _json_copy(
                    _state_value(state, "gridRowWeights", []),
                    "Grid row weights",
                ),
                "cells": cells,
                "active_cell": _state_value(state, "activeGridCell", -1),
                "selected_cells": _json_copy(
                    _state_value(state, "selectedGridCellIndices", []),
                    "Selected grid cells",
                ),
                "timeline_driver_cell": _state_value(
                    state, "timelineDriverCell", -1
                ),
            },
            "visualization": {
                "scalar_plot_policy": str(
                    _state_value(state, "scalarPlotPolicy", "always") or "always"
                ),
            },
        },
    }


def workspace_json(state, campaign_path: str) -> str:
    try:
        return (
            json.dumps(
                workspace_document(state, campaign_path),
                allow_nan=False,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
    except (TypeError, ValueError) as e:
        raise WorkspaceStateError(
            f"Workspace state is not JSON serializable: {e}"
        ) from e


def _require_mapping(value: Any, description: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise WorkspaceStateError(f"{description} must be a JSON object")
    return value


def parse_workspace_document(content: Any) -> Dict[str, Any]:
    """Parse and validate the outer structure of a workspace JSON document."""

    if isinstance(content, bytes):
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as e:
            raise WorkspaceStateError("State file must be UTF-8 JSON") from e
    elif isinstance(content, str):
        text = content
    else:
        raise WorkspaceStateError("State file content must be text or bytes")

    try:
        value = json.loads(
            text,
            parse_constant=_invalid_json_constant,
        )
    except (json.JSONDecodeError, ValueError) as e:
        raise WorkspaceStateError(f"Invalid JSON: {e}") from e

    document = _require_mapping(value, "State file")
    if document.get("format") != WORKSPACE_FORMAT:
        raise WorkspaceStateError(
            f'Unsupported state format: {document.get("format")!r}'
        )
    if document.get("version") != WORKSPACE_VERSION:
        raise WorkspaceStateError(
            "Unsupported state version: "
            f"{document.get('version')!r}; expected {WORKSPACE_VERSION}"
        )

    campaign = _require_mapping(document.get("campaign"), "campaign")
    campaign_name = campaign.get("name")
    if not isinstance(campaign_name, str) or not campaign_name.strip():
        raise WorkspaceStateError("campaign.name must be a non-empty string")

    saved_state = _require_mapping(document.get("state"), "state")
    _require_mapping(saved_state.get("catalog"), "state.catalog")
    grid = _require_mapping(saved_state.get("grid"), "state.grid")
    _require_mapping(saved_state.get("visualization"), "state.visualization")

    cells = grid.get("cells")
    if not isinstance(cells, list):
        raise WorkspaceStateError("state.grid.cells must be a JSON array")
    if len(cells) > 64:
        raise WorkspaceStateError("state.grid.cells exceeds the 8x8 grid limit")
    for index, cell in enumerate(cells):
        if not isinstance(cell, dict):
            raise WorkspaceStateError(
                f"state.grid.cells[{index}] must be a JSON object"
            )

    return document


def validate_workspace_campaign(
    document: Dict[str, Any], campaign_path: str
) -> None:
    saved_name = str(document.get("campaign", {}).get("name", "") or "")
    current_name = Path(str(campaign_path or "")).name
    if saved_name != current_name:
        raise WorkspaceStateError(
            f'State file is for campaign "{saved_name}", '
            f'not "{current_name or campaign_path}"'
        )
