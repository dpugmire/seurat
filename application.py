from typing import Any, Dict, List, Literal, Optional, TypedDict


NavigationView = Literal["variables", "objects", "campaign"]


class NavigationResource(TypedDict, total=False):
    variable_id: str
    name: str
    label: str
    path: str
    source_dataset: str


class NavigationNode(TypedDict):
    id: str
    kind: str
    label: str
    resource: Optional[NavigationResource]
    children: List["NavigationNode"]
    has_children: bool
    count: Optional[int]


class NavigationRequest(TypedDict, total=False):
    view: NavigationView
    query: Dict[str, Any]
    only_visualized: bool
    parent_id: Optional[str]


class SeuratApplication:
    """Backend application facade used by Trame controller adapters."""

    def __init__(self, campaign_db):
        self._campaign_db = campaign_db

    def get_navigation(self, request: NavigationRequest) -> List[NavigationNode]:
        view = str(request.get("view", "variables") or "variables")
        if view != "variables":
            raise ValueError(f"Unsupported navigation view: {view}")

        query = request.get("query") or None
        only_visualized = bool(request.get("only_visualized", False))
        groups = self._campaign_db.grouped_variable_names(
            extra_filter=query,
            only_visualized=only_visualized,
        )
        return self._variable_navigation(groups)

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
                    "source_dataset": str(variable.get("source_dataset", "") or ""),
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
