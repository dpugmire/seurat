from typing import List, Optional

from seurat.backends import (
    BackendStatus,
    CatalogBackend,
    LocalCampaignBackend,
    NavigationNode,
    NavigationRequest,
    NavigationResource,
    NavigationView,
)


class SeuratApplication:
    """Backend application facade used by Trame controller adapters."""

    def __init__(
        self,
        campaign_db=None,
        *,
        backend: Optional[CatalogBackend] = None,
    ):
        if backend is None:
            if campaign_db is None:
                raise TypeError("SeuratApplication requires a backend or campaign_db")
            backend = LocalCampaignBackend(campaign_db)
        self._backend = backend

    def get_navigation(self, request: NavigationRequest) -> List[NavigationNode]:
        return self._backend.get_navigation(request)

    def get_backend_status(self) -> BackendStatus:
        return self._backend.get_status()


__all__ = (
    "BackendStatus",
    "CatalogBackend",
    "NavigationNode",
    "NavigationRequest",
    "NavigationResource",
    "NavigationView",
    "SeuratApplication",
)
