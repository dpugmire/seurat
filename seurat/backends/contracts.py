"""Backend-neutral contracts used by Seurat's application layer."""

from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Protocol, TypedDict


NavigationView = Literal["variables", "files", "objects", "campaign"]
CatalogFilter = Dict[str, Any]


class NavigationResource(TypedDict, total=False):
    file_count: int
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
    query: CatalogFilter
    only_visualized: bool
    parent_id: Optional[str]


@dataclass(frozen=True)
class BackendStatus:
    """Availability reported without exposing backend implementation details."""

    ok: bool
    error: str = ""


class CatalogBackend(Protocol):
    """The catalog capability required by Seurat's Trame application."""

    def get_navigation(self, request: NavigationRequest) -> List[NavigationNode]:
        """Return normalized catalog navigation for one request."""

        ...

    def get_status(self) -> BackendStatus:
        """Return the backend availability visible to the catalog UI."""

        ...
