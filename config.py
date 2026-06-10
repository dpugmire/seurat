import os

SEURAT_SQLITE_DB = os.getenv("SEURAT_SQLITE_DB", "")
SEURAT_CACHE_DIR = os.getenv("SEURAT_CACHE_DIR", "~/.cache/seurat")

CAMPAIGN_PATH = os.getenv("CAMPAIGN_PATH", "kh.aca")

SOURCE_FIELDS = ["source_dataset", "producer", "casename", "file", "min", "max"]

MOVIE_FPS = int(os.getenv("MOVIE_FPS", "2"))
MAX_MOVIE_FRAMES = int(os.getenv("MAX_MOVIE_FRAMES", "240"))
