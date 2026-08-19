import os

SEURAT_SQLITE_DB = os.getenv("SEURAT_SQLITE_DB", "")
SEURAT_CACHE_DIR = os.getenv("SEURAT_CACHE_DIR", "~/.cache/seurat")
SEURAT_INTERACTION_LOG_DIR = os.getenv("SEURAT_INTERACTION_LOG_DIR", "").strip()
SEURAT_INTERACTION_LOG_MAX_MB = int(
    os.getenv("SEURAT_INTERACTION_LOG_MAX_MB", "64")
)
SEURAT_PREFERENCE_PROFILE = os.getenv("SEURAT_PREFERENCE_PROFILE", "").strip()
SEURAT_PREFERENCE_MODE = os.getenv("SEURAT_PREFERENCE_MODE", "off").strip().lower()
SEURAT_PREFERENCE_MIN_EVIDENCE = float(
    os.getenv("SEURAT_PREFERENCE_MIN_EVIDENCE", "3")
)
SEURAT_PREFERENCE_MIN_SESSIONS = int(
    os.getenv("SEURAT_PREFERENCE_MIN_SESSIONS", "2")
)
SEURAT_PREFERENCE_MIN_CONFIDENCE = float(
    os.getenv("SEURAT_PREFERENCE_MIN_CONFIDENCE", "0.67")
)
SEURAT_PREFERENCE_MIN_MARGIN = float(
    os.getenv("SEURAT_PREFERENCE_MIN_MARGIN", "0.15")
)

CAMPAIGN_PATH = os.getenv("CAMPAIGN_PATH", "kh.aca")

SOURCE_FIELDS = ["source_dataset", "producer", "casename", "file", "min", "max"]

MOVIE_FPS = int(os.getenv("MOVIE_FPS", "2"))
MAX_MOVIE_FRAMES = int(os.getenv("MAX_MOVIE_FRAMES", "240"))

SEURAT_LLM_MODEL = os.getenv("SEURAT_LLM_MODEL", "").strip()
SEURAT_LLM_API_KEY = os.getenv("SEURAT_LLM_API_KEY", "ollama").strip()
SEURAT_LLM_BASE_URL = os.getenv(
    "SEURAT_LLM_BASE_URL", "http://localhost:11434/v1"
).strip()
SEURAT_LLM_TIMEOUT_SECONDS = float(
    os.getenv("SEURAT_LLM_TIMEOUT_SECONDS", "30")
)
