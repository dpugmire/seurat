import os

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "catnip_campaigns")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "campaign_entries")

CAMPAIGN_PATH = os.getenv("CAMPAIGN_PATH", "kh.aca")

SOURCE_FIELDS = ["producer", "casename", "file", "min", "max"]

MOVIE_FPS = int(os.getenv("MOVIE_FPS", "2"))
MAX_MOVIE_FRAMES = int(os.getenv("MAX_MOVIE_FRAMES", "240"))
