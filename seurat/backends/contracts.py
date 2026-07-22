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


class SourceDescriptor(TypedDict, total=False):
    """Backend-neutral description of one variable source/run."""

    id: str
    label: str
    variable_id: str
    variable_name: str
    variable_type: str
    variable_path: str
    source_dataset: str
    source_datasets: List[str]
    files: List[str]
    producer: str
    casename: str
    file: str
    schema_name: str
    schema_file_group: str
    schema_role: str
    schema_mode: str
    num_timesteps: int
    visualization_name: str
    visualization_kind: str
    visualization_source_dataset: str
    association_source: str
    campaign_path: str
    variable_location: str
    frame_index: Optional[int]
    minimum: Optional[float]
    maximum: Optional[float]


class SourceSummary(TypedDict):
    variable_id: str
    num_sources: int
    global_min: Optional[float]
    global_max: Optional[float]
    mean_min: Optional[float]
    mean_max: Optional[float]
    median_min: Optional[float]
    median_max: Optional[float]
    sources: List[SourceDescriptor]


class SourceSummaryRequest(TypedDict, total=False):
    variable_id: str
    query: CatalogFilter


class SourceLookupRequest(TypedDict, total=False):
    variable_id: str
    visualization_name: str
    query: CatalogFilter


class SourceRestrictionRequest(TypedDict, total=False):
    queries: List[CatalogFilter]


class SourceRestrictionResult(TypedDict):
    """Resolved legacy query used until Phase 5B.2 formalizes filters."""

    query: CatalogFilter
    count: int


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


class SourceBackend(Protocol):
    """Source discovery and summary capability used by Seurat."""

    def get_source_summary(self, request: SourceSummaryRequest) -> SourceSummary:
        """Return normalized source rows and statistics for one variable."""

        ...

    def find_source(
        self, request: SourceLookupRequest
    ) -> Optional[SourceDescriptor]:
        """Find a source that provides a requested stored visualization."""

        ...

    def resolve_source_restriction(
        self, request: SourceRestrictionRequest
    ) -> SourceRestrictionResult:
        """Resolve source clauses for the current compatibility query path."""

        ...


class SeuratBackend(CatalogBackend, SourceBackend, Protocol):
    """Capabilities required by the current Seurat application facade."""

    pass
