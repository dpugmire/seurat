# Seurat

This is a small Trame (Vue3) application for viewing ADIOS campaign data.
On startup, it reads a `.aca` campaign file into a Seurat SQLite sidecar DB and
provides a UI to browse variables, view min/max summaries, filter with a simple
query language, and preview image sequences as short videos.

## Architecture

`seurat.app.SeuratApp` is the composition root. It owns the Trame server,
enables Seurat's web module, initializes state, connects the data access layer
to controller adapters, and constructs the UI. The top-level `app.py`, `ui.py`,
and `state_init.py` modules remain compatibility entry points.

The main architectural boundaries are:

- `seurat/components/`: composable `TrameComponent` UI sections. The root UI
  owns the query toolbar, variable catalog, grid workspace, dialogs/settings,
  and context menu.
- `seurat/module/`: registered JavaScript and CSS assets served by Trame. Web
  identifiers use the `seurat` namespace and assets are included in wheels.
- `seurat/widgets.py`: Python wrappers for Seurat's registered Vue components.
  The grid runtime component coordinates focused timeline, media, and plot
  lifecycles. The timeline runtime owns timeline selection, VCR controls,
  image/video synchronization, timers, and media observation. The media runtime
  owns pan/zoom and reset-view observation. The plot runtime owns plot-data
  parsing, SVG rendering, cursor drawing, hover/pan/zoom interactions, and
  render observation. The interaction runtime owns app-scoped variable/grid
  drag-and-drop, context menus, and floating-panel movement. The resize runtime
  owns variable-panel and grid-track resizing, including pointer capture. All
  runtimes release their listeners, observers, timers, pointer state, and
  transient styling on unmount.
- `seurat/models/`: pure, dependency-free grid, timeline, and source-selection
  behavior, plus plot, plugin-option, and grid-layout normalization. Controllers
  adapt Trame state to these testable operations.
- `seurat/state/`: explicit, non-overlapping state ownership for catalog,
  sources, visualization settings, grid/timeline, and context menus.
- `seurat/controllers/`: Trame-facing adapters organized by catalog, source,
  grid, visualization, context-menu, and lifecycle ownership. Each domain
  declares the actions, triggers, and state-change callbacks it registers.
- `seurat/backends/`: backend-neutral capability contracts and the current
  local ACA/SQLite adapter. Catalog navigation, availability, source
  descriptors, source statistics, and source restriction resolution now route
  through this seam; later query, media, and compute capabilities remain
  documented in [PHOBOS_INTEGRATION.md](PHOBOS_INTEGRATION.md).
- `application.py`: application facade over the injected backend capabilities;
  it retains compatibility exports for the typed navigation and source
  contracts.
- `controllers.py`: compatibility exports for the packaged controller adapters.
- `ingest_campaign.py`, `sqlite_store.py`, and `db.py`: ACA ingestion, SQLite
  collection compatibility, and campaign data access/rendering.

Keep domain decisions in `seurat/models/` and state defaults in the owning
`seurat/state/` module. Keep Trame callbacks and their registration declarations
in the matching `seurat/controllers/` domain. UI components should bind state
and controller actions, not duplicate those decisions in markup or browser
code. Backend implementations should return normalized application DTOs rather
than exposing collection documents, ACA paths, or remote API objects to Trame
controllers. See [PHOBOS_INTEGRATION.md](PHOBOS_INTEGRATION.md) for the planned
Phobos boundary and remaining migration phases.

Client-side event and observer ownership is lifecycle-scoped rather than
document-global. The registered runtimes own grid timeline/VCR behavior,
variable/grid drag-and-drop, context menus, floating-panel movement,
variable-panel and grid-track resizing, media pan/zoom, plot interaction, and
plot rendering observation. Timeline/VCR policy lives in
`seurat/module/serve/seurat-timeline-runtime.js`; media pan/zoom and its reset
observer live in `seurat/module/serve/seurat-media-runtime.js`; plot parsing,
SVG rendering, and plot interaction live in
`seurat/module/serve/seurat-plot-runtime.js`. The small
`seurat/module/serve/seurat.js` coordinator mounts these domains and connects
combined reset/cursor behavior. Internal runtime objects are collected under
`window.seurat.runtimes`; existing top-level aliases remain for Trame Vue plugin
registration compatibility.

## Run

Requirements (at minimum):

- Python deps: `trame`, `trame-vuetify`, `adios2`, `numpy`, `Pillow`.
- Optional for YAML campaign and image-association schemas: `pyyaml`.
- `ffmpeg` available on PATH for movie preview tiles.

Image sequence bytes are loaded lazily from the ACA file when a preview tile is
built. The SQLite sidecar stores frame metadata and ADIOS variable paths, not
copied image blobs.

Install the Python dependencies from this repo:

```bash
python -m pip install -e ".[schema]"
```

Install the browser-test dependencies and Chromium with:

```bash
python -m pip install -e ".[schema,test]"
python -m playwright install chromium
```

The browser tests are opt-in so the normal suite remains fast and does not
require a browser installation:

```bash
SEURAT_RUN_BROWSER_TESTS=1 python -m pytest -q tests/browser
```

The deterministic browser fixture does not require a campaign archive. It
exercises application mounting, variable grouping, grid selection and
assignment, layout controls, context menus, rendering, and both schema-less
step-index and declared physical-time timelines in a real Chromium client. It
also covers variable-panel and grid-track resizing, pointer capture, cleanup,
and idempotent runtime remounting. Floating-panel movement, media pan/zoom,
plot hover/pan/zoom, reset requests, observer teardown, and render-timer cleanup
are exercised through the same mounted-client suite.

Example:

```bash
python app.py campaign.aca

# Optional: supply a campaign schema when schema.yaml is not embedded
python app.py campaign.aca --campaign-schema schema.yaml

# Optional: pass image association schema text/YAML
python app.py campaign.aca --image-association-schema image_variable_map.yaml
```

By default, Seurat stores its viewer sidecar DB under `~/.cache/seurat` using a
filename derived from the resolved campaign path. Override the location with:

```bash
export SEURAT_CACHE_DIR=/path/to/cache-dir
export SEURAT_SQLITE_DB=/path/to/viewer-cache.sqlite
```

## Embedded Campaign Schema

Seurat reads a text dataset named `schema.yaml` from the campaign archive. A
time-series group written by appending steps to one ADIOS dataset can select
either one exact campaign dataset with `path` or multiple datasets with
`pattern`. Each matched append-mode dataset resolves its time variable relative
to itself.

For example, this schema associates every BOUT++ simulation and analysis
dataset with its own appended `wtime` values:

```yaml
schema_version: 1
name: boutpp-selected-runs

time:
  variable: wtime

files:
  simulations:
    role: time_series
    mode: append
    pattern: "runs/**/simulation"

  analyses:
    role: time_series
    mode: append
    pattern: "runs/**/analysis"
```

Embedding the schema keeps it available when the campaign is copied to another
system. For archives without an embedded schema, pass the same schema explicitly
with `--campaign-schema path/to/schema.yaml`.

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

## Plugins

Seurat loads built-in plugins from `seurat_plugins/` and personal plugins from:

```text
~/.seurat/plugins
```

Add more personal plugin search directories with a colon-separated environment
variable:

```bash
export SEURAT_PLUGIN_PATH=~/.seurat/plugins:/path/to/other/plugins
```

Each plugin is a Python file. Files whose names start with `_` are ignored.
Broken personal plugins are skipped and reported on stderr so one bad local
plugin does not prevent Seurat from starting.

Minimal variable plugin:

```python
PLUGIN_ID = "my_profile_plugin"
LABEL = "My profile plugin"
PLUGIN_SCOPE = "variable"  # default

def supports(meta):
    return meta.get("ndims") == 1

def options_schema(meta):
    return []

def render(ctx):
    helpers = ctx["helpers"]
    # Return a Seurat tile dict, for example media_type="plot1d".
    ...
```

Minimal source/run plugin:

```python
PLUGIN_ID = "my_source_plugin"
LABEL = "My source plugin"
PLUGIN_SCOPE = "source"

def supports_context(meta):
    return "my_file.bp" in meta.get("source_dataset", "")

def options_schema(meta):
    return []

def render(ctx):
    # Return a Seurat tile dict, for example media_type="image".
    ...
```

Variable plugins appear as `plugin:<id>` visualization choices for compatible
variables. Source plugins appear in the tile right-click menu under `Run
Plugin` for compatible source contexts.

Current cache note: the app currently drops and re-ingests the sidecar each time
it starts. The sidecar is metadata-only for image frames, but the next cache
phase should skip ingest when the ACA file is unchanged.

## TODO

- Query/source restriction errors: `source(...)` resolution should propagate DB
  errors to the UI instead of reporting a successful query with zero source
  runs.
- Query language validation: require `in` and `not in` to use a list/tuple
  right-hand side so Mongo query behavior and local source-filter behavior stay
  identical.
- Query language validation: restrict `contains(field, text)` to text fields
  such as `var`, `id`, `source`, `dataset`, `producer`, `casename`, `file`,
  visualization names, and paths.
- Source Filter field parity: either enrich source rows with visualization
  metadata so fields like `visualization_name` and `frame_index` work locally,
  or document that those fields are Query-only.
- Source restriction identity: use a compound source/run identity instead of
  preferring `producer` alone, so reused producer names across cases/files do
  not over-include unrelated sources.
