# Seurat

This repository contains the active Trame/Vue3 campaign viewer for ADIOS
campaign archives. Use `app.py` as the main entrypoint. The older prototype
files, including `catnip_db_app.py`, `catnip_parse_db.py`, and
`catnip_tree_app.py`, should not be treated as the supported application path
unless the user explicitly asks to work on them.

## From-Scratch Setup

Start from this repository:

```bash
cd /Users/dpn/proj/seurat
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Equivalent editable install:

```bash
python -m pip install -e ".[schema]"
```

The `schema` extra installs `PyYAML`, which is only needed for YAML image
association schemas.

## External Services And Tools

The app needs MongoDB and `ffmpeg` in addition to the Python packages.

- MongoDB must be reachable through `MONGO_URI`; local default is
  `mongodb://localhost:27017`.
- `ffmpeg` must be available on `PATH` for movie preview tiles.
- ADIOS2 must be importable as Python package `adios2`.

Useful checks:

```bash
command -v ffmpeg
python -c "import adios2, numpy, pymongo, trame; from PIL import Image"
```

On macOS with Homebrew, one possible local setup is:

```bash
brew install ffmpeg mongodb-community
brew services start mongodb-community
```

Use whatever MongoDB installation method is appropriate for the machine.

## Runtime Configuration

The defaults are defined in `config.py`:

```bash
export MONGO_URI="mongodb://localhost:27017"
export MONGO_DB="catnip_campaigns"
export MONGO_COLLECTION="campaign_entries"
export MOVIE_FPS="2"
export MAX_MOVIE_FRAMES="240"
```

Important: `app.py` drops and re-ingests the configured Mongo collection each
time the server starts. Do not point `MONGO_COLLECTION` at data that should be
preserved.

## Run The App

Run against a campaign archive:

```bash
source .venv/bin/activate
python app.py /path/to/campaign.aca
```

If installed editably, the console script is also available:

```bash
seurat /path/to/campaign.aca
```

If using an image association schema:

```bash
python app.py /path/to/campaign.aca --image-association-schema /path/to/image_variable_map.yaml
```

Trame prints the local browser URL when the server starts, commonly on port
`8080`.

## Data Model Notes

Campaigns created with the hpc-campaign visualization API are associated through
the ACA `visualization_*` metadata tables. Seurat treats `variable_id` as a
source-independent variable identity, while source-specific datasets remain
distinguished by `source_dataset`.

Legacy image path parsing is still used as a fallback for older campaigns.

## Quick Verification

Before handing changes back, use targeted checks when possible:

```bash
python -m py_compile app.py ingest_campaign.py db.py controllers.py ui.py
python -m pip check
```

If MongoDB, ADIOS2, or `ffmpeg` are unavailable in the environment, state that
explicitly and report which verification was skipped.
