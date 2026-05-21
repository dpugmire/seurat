# Seurat

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
- Python deps: `pymongo`, `trame`, `trame-vuetify`, `adios2`, `numpy`, `Pillow`.
- Optional for schema-driven image associations: `pyyaml`.
- `ffmpeg` available on PATH for movie preview tiles.

Install the Python dependencies from this repo:

```bash
python -m pip install -e ".[schema]"
```

Example:

```bash
export MONGO_URI="mongodb://localhost:27017"
export MONGO_DB="catnip_campaigns"
export MONGO_COLLECTION="campaign_entries"

python app.py campaign.aca

# Optional: pass image association schema text/YAML
python app.py campaign.aca --image-association-schema image_variable_map.yaml
```

Visualization association notes:

- Campaigns created with the new hpc-campaign visualization API are associated through the ACA `visualization_*` metadata tables.
- Seurat treats `variable_id` as a source-independent variable identity. Different source datasets for that same variable remain separate through the `source_dataset` field.
- For visualization API images, `variable_id` comes from `visualization_variable.variable_name`.
- Legacy image path parsing is still used as a fallback for older campaigns.
- Longer term, the viewer should use an explicit display/grouping schema that separates the raw source variable name, the viewer display label, the variable grouping id, and the source dataset. Until that exists, the campaign variable name is used directly for both grouping and display.

Schema notes (`image_variable_map.yaml`):

- `rules` map image logical paths to `variable_name` + `visualization_name`.
- Optional `physical_to_logical` maps file variable names to logical names.

Example:

```yaml
schema_version: 1
physical_to_logical:
  exact:
    hll_pressure: pressure
  regex:
    - pattern: "^hll_(.+)$"
      replace: "\\1"
```

The app will drop and re-ingest the collection each time it starts.
