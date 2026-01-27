# Catnip Campaign DB Viewer

This is a small Trame (Vue3) application for viewing ADIOS campaign data.
On startup, it reads a `.aca` campaign file. It puts the data into a Mongo DB and provides a UI to browse variables, view min/max summaries, filter with a simple query language, and preview image sequences as short videos.

High-level structure:

- `app.py`: entrypoint; connects to Mongo, boots Trame, wires controllers/UI.
- `ingest_campaign.py`: reads a `.aca` file via ADIOS2 and writes documents to Mongo.
- `db.py`: data access helpers for summaries and movie tiles.
- `controllers.py`: Trame callbacks (querying, selection, ingest-on-start).
- `ui.py`: Vuetify3 UI layout.

## Run

Requirements (at minimum):

- MongoDB running locally (or set `MONGO_URI`).
- Python deps: `pymongo`, `trame`, `adios2`, `numpy`, `Pillow`.
- `ffmpeg` available on PATH for movie preview tiles.

Example:

```bash
export MONGO_URI="mongodb://localhost:27017"
export MONGO_DB="catnip_campaigns"
export MONGO_COLLECTION="campaign_entries"

python app.py campaign.aca
```

The app will drop and re-ingest the collection each time it starts.
