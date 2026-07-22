"""Explicit runtime dependencies shared by Seurat controller adapters."""

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ControllerContext:
    server: Any
    db: Any
    collection: Any
    parse_campaign: Callable[..., Any]
    campaign_path: str
    image_association_schema_path: str = ""
    campaign_schema_path: str = ""
