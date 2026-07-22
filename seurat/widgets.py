"""Seurat client widgets registered by the Trame web module."""

from trame_client.widgets.core import AbstractElement


class GridRuntime(AbstractElement):
    """Lifecycle owner for browser-only grid and timeline interactions."""

    def __init__(self, children=None, **kwargs):
        super().__init__("seurat-grid-runtime", children, **kwargs)


class InteractionRuntime(AbstractElement):
    """Lifecycle owner for catalog/grid drag-and-drop and context menus."""

    def __init__(self, children=None, **kwargs):
        super().__init__("seurat-interaction-runtime", children, **kwargs)
