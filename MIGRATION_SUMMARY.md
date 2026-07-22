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

## Current Git State

The Trame rearchitecture work is on:

```text
branch: rearchitect-trame-phase2
remote: origin -> https://github.com/dpugmire/seurat.git
```

Phase 1 was merged into `main` by GitHub PR #4 at merge commit
`82fd7bc660bd07cca1ba0965b80742b6ed24f0a4`. Phase 2 decomposes the remaining
controller closure into domain-owned Trame adapters and extracts pure controller
logic into testable model modules.

The last commit before the rearchitecture is preserved by the annotated tag:

```text
pre-rearchitect-trame-phase1 -> fe0926f7a7ccb5fe012816f9fc962edf0a8588f3
```

The original repo still has the subtree split branch used to create this repo:

```text
seurat-split
```

## What Was Done

- Created a subtree split from the original viewer subdirectory.
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

The new repo contains the tracked viewer source from the original viewer,
including:

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

Untracked prototypes, generated `.aca` files, data directories, simulation
outputs, build directories, caches, and editor metadata from the original repo
were not moved into `seurat`.

Unsupported tracked prototype applications inherited by the initial split were
removed before the Trame architecture work began.

## Verification

The standard verification commands are:

```bash
python -m py_compile app.py config.py controllers.py db.py ingest_campaign.py media_utils.py query_parser.py state_init.py ui.py
python -m pytest -q
python -m pip check
```

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
- Internal legacy branding from the original viewer was removed during the
  first Trame rearchitecture phase.
