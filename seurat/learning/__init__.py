"""Local interaction logging and preference learning for Seurat."""

from .builder import build_preference_profile
from .events import EVENT_SCHEMA_VERSION, EVENT_TYPES, new_identifier, validate_event
from .log import InteractionLog
from .profile import (
    PREFERENCE_PROFILE_SCHEMA_VERSION,
    PreferenceProfile,
    VisualizationRecommendation,
    WorkspaceRecommendation,
    normalize_preference_mode,
)

__all__ = (
    "EVENT_SCHEMA_VERSION",
    "EVENT_TYPES",
    "InteractionLog",
    "PREFERENCE_PROFILE_SCHEMA_VERSION",
    "PreferenceProfile",
    "VisualizationRecommendation",
    "WorkspaceRecommendation",
    "build_preference_profile",
    "new_identifier",
    "normalize_preference_mode",
    "validate_event",
)
