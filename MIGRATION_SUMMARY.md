# Seurat Migration Summary

This repo was created by splitting the viewer code out of the original
`campaign_viewer` repository.

## Current Repositories

New local repo:

```text
/Users/dpn/proj/seurat
```

GitHub repo:

```text
https://github.com/dpugmire/seurat
```

Original repo:

```text
/Users/dpn/proj/campaign_viewer/campaign_viewer
```

Original viewer path:

```text
/Users/dpn/proj/campaign_viewer/campaign_viewer/catnip_db
```

## Current Git State

The new `seurat` repo is on:

```text
branch: main
remote: origin -> https://github.com/dpugmire/seurat.git
status: clean before this summary file was added
```

The most recent setup commit before this file was:

```text
6c4dbf1 Set up seurat repository metadata
```

The original repo still has the subtree split branch used to create this repo:

```text
seurat-split
```

## What Was Done

- Created a subtree split from `catnip_db`.
- Cloned that split history into `/Users/dpn/proj/seurat`.
- Renamed the new repo branch to `main`.
- Removed the temporary local remote pointing back to the old repo.
- Added a new GitHub remote for `dpugmire/seurat`.
- Created and pushed the public GitHub repository.
- Added repo metadata:
  - `.gitignore`
  - `pyproject.toml`
  - updated `README.md`

## Included Source

The new repo contains the tracked viewer source from `catnip_db`, including:

- `app.py`
- `config.py`
- `controllers.py`
- `db.py`
- `ingest_campaign.py`
- `media_utils.py`
- `query_parser.py`
- `state_init.py`
- `ui.py`
- `README.md`

Legacy tracked files from the split were also retained:

- `catnip_db_app.py`
- `catnip_parse_db.py`
- `catnip_tree_app.py`

Untracked prototypes, generated `.aca` files, data directories, simulation
outputs, build directories, caches, and editor metadata from the original repo
were not moved into `seurat`.

## Verification

The Python compile check passed:

```bash
python3 -m py_compile app.py config.py controllers.py db.py ingest_campaign.py media_utils.py query_parser.py state_init.py ui.py catnip_db_app.py catnip_parse_db.py catnip_tree_app.py
```

The initial `python3 app.py --help` smoke test was blocked because the active
Python environment did not have `pymongo` installed. The dependency is now
declared in `pyproject.toml`.

Install the repo dependencies with:

```bash
cd /Users/dpn/proj/seurat
python -m pip install -e ".[schema]"
```

Then run:

```bash
python app.py --help
```

## Notes

- The original `campaign_viewer` repo was not cleaned up.
- Existing untracked simulation/data/prototype files in the original repo were
  left untouched.
- No internal `catnip_*` identifiers were renamed during the migration.
