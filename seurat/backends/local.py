"""Local ACA/SQLite implementation of Seurat backend capabilities."""

from typing import Any, Dict, List

from .contracts import (
    BackendStatus,
    NavigationNode,
    NavigationRequest,
    NavigationResource,
)


class LocalCampaignBackend:
    """Adapt the existing ``CampaignDb`` to backend-neutral contracts."""

    def __init__(self, campaign_db):
        self._campaign_db = campaign_db

    def get_status(self) -> BackendStatus:
        return BackendStatus(
            ok=bool(getattr(self._campaign_db, "ok", False)),
            error=str(getattr(self._campaign_db, "last_error", "") or ""),
        )

    def get_navigation(self, request: NavigationRequest) -> List[NavigationNode]:
        view = str(request.get("view", "variables") or "variables")
        query = request.get("query") or None
        only_visualized = bool(request.get("only_visualized", False))
        if view == "variables":
            groups = self._campaign_db.grouped_variable_names(
                extra_filter=query,
                only_visualized=only_visualized,
            )
            return self._variable_navigation(groups)
        if view == "files":
            groups = self._campaign_db.grouped_variables_by_source_dataset(
                extra_filter=query,
                only_visualized=only_visualized,
            )
            return self._file_navigation(groups)
        raise ValueError(f"Unsupported navigation view: {view}")

    @staticmethod
    def _variable_navigation(groups: List[Dict[str, Any]]) -> List[NavigationNode]:
        navigation: List[NavigationNode] = []
        for group in groups:
            group_label = str(group.get("name", "") or "")
            children: List[NavigationNode] = []
            for variable in group.get("variables", []) or []:
                variable_id = str(variable.get("id", "") or "")
                if not variable_id:
                    continue
                label = str(
                    variable.get("label", "")
                    or variable.get("name", "")
                    or variable_id
                )
                resource: NavigationResource = {
                    "variable_id": variable_id,
                    "name": str(variable.get("name", "") or ""),
                    "label": label,
                    "path": str(variable.get("path", "") or ""),
                    "source_dataset": str(
                        variable.get("source_dataset", "") or ""
                    ),
                }
                children.append(
                    {
                        "id": f"variable:{variable_id}",
                        "kind": "variable",
                        "label": label,
                        "resource": resource,
                        "children": [],
                        "has_children": False,
                        "count": None,
                    }
                )

            if not children:
                continue
            navigation.append(
                {
                    "id": f"variable-group:{group_label}",
                    "kind": "variable-group",
                    "label": group_label,
                    "resource": None,
                    "children": children,
                    "has_children": True,
                    "count": len(children),
                }
            )
        return navigation

    @staticmethod
    def _file_navigation(groups: List[Dict[str, Any]]) -> List[NavigationNode]:
        navigation: List[NavigationNode] = []
        for group in groups:
            source_label = str(group.get("name", "") or "")
            source_dataset = str(group.get("source_dataset", "") or "")
            file_count = int(group.get("file_count", 0) or 0)
            children: List[NavigationNode] = []
            for variable in group.get("variables", []) or []:
                variable_id = str(variable.get("id", "") or "")
                if not variable_id:
                    continue
                label = str(
                    variable.get("label", "")
                    or variable.get("name", "")
                    or variable_id
                )
                variable_source = str(
                    variable.get("source_dataset", "") or source_dataset
                )
                resource: NavigationResource = {
                    "variable_id": variable_id,
                    "name": str(variable.get("name", "") or ""),
                    "label": label,
                    "path": str(variable.get("path", "") or ""),
                    "source_dataset": variable_source,
                }
                children.append(
                    {
                        "id": f"file-variable:{source_label}:{variable_id}",
                        "kind": "variable",
                        "label": label,
                        "resource": resource,
                        "children": [],
                        "has_children": False,
                        "count": None,
                    }
                )

            if not children:
                continue
            group_resource: NavigationResource = {
                "source_dataset": source_dataset,
            }
            if file_count > 1:
                group_resource["file_count"] = file_count
            navigation.append(
                {
                    "id": f"file:{source_label}",
                    "kind": "file",
                    "label": source_label,
                    "resource": group_resource,
                    "children": children,
                    "has_children": True,
                    "count": len(children),
                }
            )
        return navigation
