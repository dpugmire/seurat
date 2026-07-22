"""Web assets served by the Seurat Trame application."""

from pathlib import Path


__all__ = ["scripts", "serve", "styles", "vue_use"]

BASE_URL = "seurat_0_1_0"

serve = {
    BASE_URL: str(Path(__file__).with_name("serve").resolve()),
}
scripts = [
    f"{BASE_URL}/seurat-media-runtime.js",
    f"{BASE_URL}/seurat.js",
    f"{BASE_URL}/seurat-grid-runtime.js",
    f"{BASE_URL}/seurat-interaction-runtime.js",
    f"{BASE_URL}/seurat-resize-runtime.js",
]
styles = [
    f"{BASE_URL}/seurat.css",
]
vue_use = ["seuratGridRuntime", "seuratInteractionRuntime", "seuratResizeRuntime"]
