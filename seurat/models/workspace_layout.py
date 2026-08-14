"""Pure helpers for Seurat's constrained pane, tab, and grid workspace."""

from copy import deepcopy
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

from seurat.models.grid import empty_grid_cell


MAX_WORKSPACE_PANES = 2
DEFAULT_PANE_ID = "pane-1"
DEFAULT_TAB_ID = "tab-1"
DEFAULT_TAB_TITLE = "View 1"


GRID_STATE_FIELDS: Tuple[Tuple[str, str], ...] = (
    ("gridRows", "rows"),
    ("gridCols", "columns"),
    ("gridLayoutMode", "layout_mode"),
    ("gridSizingMode", "sizing_mode"),
    ("gridCellSize", "cell_size"),
    ("gridMinCellSize", "minimum_cell_size"),
    ("gridMaxCellSize", "maximum_cell_size"),
    ("gridFitMinCellSize", "fit_minimum_cell_size"),
    ("gridMaxFitMinCellSize", "fit_maximum_cell_size"),
    ("gridColumnSizes", "column_sizes"),
    ("gridRowSizes", "row_sizes"),
    ("gridColumnWeights", "column_weights"),
    ("gridRowWeights", "row_weights"),
    ("gridColumnTemplate", "column_template"),
    ("gridRowTemplate", "row_template"),
    ("gridFitColumnTemplate", "fit_column_template"),
    ("gridFitRowTemplate", "fit_row_template"),
    ("gridCells", "cells"),
    ("activeGridCell", "active_cell"),
    ("selectedGridCellIndices", "selected_cells"),
    ("selectedGridCellMap", "selected_cell_map"),
    ("timelineDriverCell", "timeline_driver_cell"),
)


def grid_snapshot(state: Any) -> Dict[str, Any]:
    """Copy the complete renderable grid state from a Trame state object."""

    return {
        key: deepcopy(getattr(state, state_name, None))
        for state_name, key in GRID_STATE_FIELDS
    }


def apply_grid_snapshot(state: Any, snapshot: Mapping[str, Any]) -> None:
    """Load a grid snapshot into the legacy active-grid state fields."""

    for state_name, key in GRID_STATE_FIELDS:
        if key in snapshot:
            setattr(state, state_name, deepcopy(snapshot[key]))


def empty_grid_snapshot(snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    """Return an empty grid that retains another grid's layout preferences."""

    result = deepcopy(dict(snapshot))
    try:
        rows = max(1, min(8, int(result.get("rows", 3))))
    except Exception:
        rows = 3
    try:
        columns = max(1, min(8, int(result.get("columns", 3))))
    except Exception:
        columns = 3
    result["rows"] = rows
    result["columns"] = columns
    result["cells"] = [empty_grid_cell() for _ in range(rows * columns)]
    result["active_cell"] = -1
    result["selected_cells"] = []
    result["selected_cell_map"] = {}
    result["timeline_driver_cell"] = -1
    return result


def initial_workspace_layout(snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "split_direction": "none",
        "split_ratio": 0.5,
        "active_pane_id": DEFAULT_PANE_ID,
        "active_tab_id": DEFAULT_TAB_ID,
        "panes": [
            {
                "id": DEFAULT_PANE_ID,
                "active_tab_id": DEFAULT_TAB_ID,
                "tabs": [
                    {
                        "id": DEFAULT_TAB_ID,
                        "title": DEFAULT_TAB_TITLE,
                        "grid": deepcopy(dict(snapshot)),
                    }
                ],
            }
        ],
    }


def _next_identifier(prefix: str, identifiers: Iterable[str]) -> str:
    used = {str(value or "") for value in identifiers}
    index = 1
    while f"{prefix}-{index}" in used:
        index += 1
    return f"{prefix}-{index}"


def pane_and_tab(
    layout: Mapping[str, Any], pane_id: str, tab_id: str
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    for pane in list(layout.get("panes", []) or []):
        if str(pane.get("id", "")) != str(pane_id or ""):
            continue
        for tab in list(pane.get("tabs", []) or []):
            if str(tab.get("id", "")) == str(tab_id or ""):
                return pane, tab
        return pane, None
    return None, None


def active_pane_and_tab(
    layout: Mapping[str, Any],
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    return pane_and_tab(
        layout,
        str(layout.get("active_pane_id", "") or ""),
        str(layout.get("active_tab_id", "") or ""),
    )


def normalized_tab_title(value: Any, fallback: str) -> str:
    title = " ".join(str(value or "").split())
    return (title or fallback)[:80]


def add_workspace_tab(
    layout: Mapping[str, Any], pane_id: str, snapshot: Mapping[str, Any]
) -> Tuple[Dict[str, Any], str]:
    result = deepcopy(dict(layout))
    panes = list(result.get("panes", []) or [])
    tab_ids = [
        str(tab.get("id", ""))
        for pane in panes
        for tab in list(pane.get("tabs", []) or [])
    ]
    tab_id = _next_identifier("tab", tab_ids)
    title = f"View {len(tab_ids) + 1}"
    target = next(
        (pane for pane in panes if str(pane.get("id", "")) == str(pane_id)),
        panes[0] if panes else None,
    )
    if target is None:
        return initial_workspace_layout(snapshot), DEFAULT_TAB_ID
    target.setdefault("tabs", []).append(
        {
            "id": tab_id,
            "title": title,
            "grid": empty_grid_snapshot(snapshot),
        }
    )
    target["active_tab_id"] = tab_id
    result["active_pane_id"] = target["id"]
    result["active_tab_id"] = tab_id
    result["panes"] = panes
    return result, tab_id


def split_workspace(
    layout: Mapping[str, Any], direction: str, snapshot: Mapping[str, Any]
) -> Tuple[Dict[str, Any], Optional[str]]:
    result = deepcopy(dict(layout))
    panes = list(result.get("panes", []) or [])
    if len(panes) >= MAX_WORKSPACE_PANES:
        result["split_direction"] = (
            "vertical" if str(direction) == "vertical" else "horizontal"
        )
        return result, None

    pane_ids = [str(pane.get("id", "")) for pane in panes]
    tab_ids = [
        str(tab.get("id", ""))
        for pane in panes
        for tab in list(pane.get("tabs", []) or [])
    ]
    pane_id = _next_identifier("pane", pane_ids)
    tab_id = _next_identifier("tab", tab_ids)
    panes.append(
        {
            "id": pane_id,
            "active_tab_id": tab_id,
            "tabs": [
                {
                    "id": tab_id,
                    "title": f"View {len(tab_ids) + 1}",
                    "grid": empty_grid_snapshot(snapshot),
                }
            ],
        }
    )
    result["panes"] = panes
    result["split_direction"] = (
        "vertical" if str(direction) == "vertical" else "horizontal"
    )
    result["active_pane_id"] = pane_id
    result["active_tab_id"] = tab_id
    return result, pane_id


def close_workspace_tab(
    layout: Mapping[str, Any], pane_id: str, tab_id: str
) -> Dict[str, Any]:
    result = deepcopy(dict(layout))
    panes = list(result.get("panes", []) or [])
    total_tabs = sum(len(list(pane.get("tabs", []) or [])) for pane in panes)
    if total_tabs <= 1:
        return result

    target = next(
        (pane for pane in panes if str(pane.get("id", "")) == str(pane_id)),
        None,
    )
    if target is None:
        return result
    tabs = list(target.get("tabs", []) or [])
    removed_index = next(
        (i for i, tab in enumerate(tabs) if str(tab.get("id", "")) == str(tab_id)),
        -1,
    )
    if removed_index < 0:
        return result
    del tabs[removed_index]
    if tabs:
        target["tabs"] = tabs
        if str(target.get("active_tab_id", "")) == str(tab_id):
            target["active_tab_id"] = tabs[min(removed_index, len(tabs) - 1)]["id"]
    else:
        panes = [pane for pane in panes if pane is not target]
        result["split_direction"] = "none"

    if not panes:
        return result
    active_pane = next(
        (
            pane
            for pane in panes
            if str(pane.get("id", ""))
            == str(result.get("active_pane_id", ""))
        ),
        panes[0],
    )
    active_tab_id = str(active_pane.get("active_tab_id", "") or "")
    if not any(
        str(tab.get("id", "")) == active_tab_id
        for tab in list(active_pane.get("tabs", []) or [])
    ):
        active_tab_id = str(active_pane["tabs"][0]["id"])
        active_pane["active_tab_id"] = active_tab_id
    result["panes"] = panes
    result["active_pane_id"] = active_pane["id"]
    result["active_tab_id"] = active_tab_id
    return result


def close_workspace_pane(
    layout: Mapping[str, Any], pane_id: str
) -> Dict[str, Any]:
    result = deepcopy(dict(layout))
    panes = list(result.get("panes", []) or [])
    if len(panes) <= 1:
        return result
    closing = next(
        (pane for pane in panes if str(pane.get("id", "")) == str(pane_id)),
        None,
    )
    if closing is None:
        return result
    remaining = next(pane for pane in panes if pane is not closing)
    remaining.setdefault("tabs", []).extend(list(closing.get("tabs", []) or []))
    result["panes"] = [remaining]
    result["split_direction"] = "none"
    result["active_pane_id"] = remaining["id"]
    result["active_tab_id"] = remaining["active_tab_id"]
    return result


def move_workspace_tab(
    layout: Mapping[str, Any], pane_id: str, tab_id: str
) -> Dict[str, Any]:
    result = deepcopy(dict(layout))
    panes = list(result.get("panes", []) or [])
    if len(panes) != 2:
        return result
    source = next(
        (pane for pane in panes if str(pane.get("id", "")) == str(pane_id)),
        None,
    )
    if source is None:
        return result
    destination = next(pane for pane in panes if pane is not source)
    tabs = list(source.get("tabs", []) or [])
    tab_index = next(
        (i for i, tab in enumerate(tabs) if str(tab.get("id", "")) == str(tab_id)),
        -1,
    )
    if tab_index < 0:
        return result
    tab = tabs.pop(tab_index)
    destination.setdefault("tabs", []).append(tab)
    destination["active_tab_id"] = tab["id"]
    if tabs:
        source["tabs"] = tabs
        if str(source.get("active_tab_id", "")) == str(tab_id):
            source["active_tab_id"] = tabs[min(tab_index, len(tabs) - 1)]["id"]
    else:
        panes = [destination]
        result["split_direction"] = "none"
    result["panes"] = panes
    result["active_pane_id"] = destination["id"]
    result["active_tab_id"] = tab["id"]
    return result


def reorder_workspace_tab(
    layout: Mapping[str, Any], pane_id: str, tab_id: str, insertion_index: int
) -> Dict[str, Any]:
    """Move a tab to an insertion slot within its current pane."""

    result = deepcopy(dict(layout))
    target = next(
        (
            pane
            for pane in list(result.get("panes", []) or [])
            if str(pane.get("id", "")) == str(pane_id or "")
        ),
        None,
    )
    if target is None:
        return result

    tabs = list(target.get("tabs", []) or [])
    source_index = next(
        (
            index
            for index, tab in enumerate(tabs)
            if str(tab.get("id", "")) == str(tab_id or "")
        ),
        -1,
    )
    if source_index < 0:
        return result
    try:
        destination = max(0, min(len(tabs), int(insertion_index)))
    except (TypeError, ValueError):
        return result

    tab = tabs.pop(source_index)
    if source_index < destination:
        destination -= 1
    tabs.insert(max(0, min(len(tabs), destination)), tab)
    target["tabs"] = tabs
    return result
