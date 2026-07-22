"""Compatibility entry point for building the Seurat UI."""

from seurat.components import SeuratUI


__all__ = ["SeuratUI", "build_ui"]


def build_ui(server, refresh_variable_list=None, campaign_name=""):
    # Kept for compatibility with the original top-level application API.
    _ = refresh_variable_list
    return SeuratUI(server, campaign_name=campaign_name)
