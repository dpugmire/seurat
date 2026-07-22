"""Web assets served by the Seurat Trame application."""

from pathlib import Path


__all__ = ["scripts", "serve", "styles"]

BASE_URL = "seurat_0_1_0"

serve = {
    BASE_URL: str(Path(__file__).with_name("serve").resolve()),
}
scripts = [
    f"{BASE_URL}/seurat.js",
]
styles = [
    f"{BASE_URL}/seurat.css",
]
