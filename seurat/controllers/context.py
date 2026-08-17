"""Explicit runtime dependencies shared by Seurat controller adapters."""

from dataclasses import dataclass
from typing import Any, Callable, Optional

from seurat.backends import SeuratBackend
from seurat.query_assistant import QueryTranslator


@dataclass(frozen=True)
class ControllerContext:
    server: Any
    backend: SeuratBackend
    db: Any
    collection: Any
    parse_campaign: Callable[..., Any]
    campaign_path: str
    image_association_schema_path: str = ""
    campaign_schema_path: str = ""
    query_translator: Optional[QueryTranslator] = None
    interaction_log: Optional[Any] = None
