# Seurat Architecture

This diagram shows the current local application path and the planned Phobos
capability path. Solid arrows represent implemented relationships. Dashed
arrows and nodes labeled "planned" represent future work.

```mermaid
%%{init: {"flowchart": {"nodeSpacing": 80, "rankSpacing": 85, "curve": "basis"}, "themeVariables": {"fontSize": "16px"}}}%%
flowchart TB
  Client["Trame Vue client<br/>Renders toolbar, catalog, grid, dialogs, plots, and media<br/>Widgets bind state; JS runtimes own browser interactions"]
  State["Trame state<br/>Serializable UI state shared by Python and the browser<br/>Catalog, sources, grid, timeline, settings, and menus"]
  Controllers["Domain controllers<br/>Receive UI actions and state changes<br/>Call domain logic and application operations<br/>Write normalized results back to Trame state"]

  Models["Pure domain logic<br/>Deterministic grid, source, timeline, plot, and plugin rules<br/>No Trame, database, ACA, or Phobos dependencies<br/>Directly unit-testable"]
  Facade["SeuratApplication facade<br/>Backend-neutral operations used by controllers<br/>Hides local documents, ACA paths, Django objects,<br/>and REST response formats"]

  Capabilities["Backend capabilities<br/>Catalog: navigation and availability · Sources: descriptors and statistics<br/>Query: paused for redesign · Media and jobs: planned<br/>Contracts return normalized Seurat data-transfer objects"]

  LocalBackend["LocalCampaignBackend<br/>Implements the capability contracts for a local campaign<br/>Translates normalized requests and results<br/>without exposing local storage above this boundary"]
  PhobosBackend["Future PhobosBackend<br/>Will implement the same capability contracts<br/>using authenticated Phobos APIs<br/>UI and controllers remain unchanged"]

  LocalServices["Local campaign services<br/>CampaignDb: discovery, reads, summaries, and rendering<br/>SQLite sidecar and ingestion · ACA and ADIOS2 payloads<br/>ffmpeg movie previews"]
  PhobosServices["Phobos services<br/>Authentication and authorization · campaign/foray/variable APIs<br/>Authorized media delivery · background jobs<br/>Durable persistence, workers, and artifacts"]

  Client <--> State
  State <--> Controllers
  Controllers --> Models
  Controllers --> Facade
  Facade --> Capabilities

  Capabilities --> LocalBackend
  Capabilities -. planned .-> PhobosBackend
  LocalBackend --> LocalServices
  PhobosBackend -. planned .-> PhobosServices

  Controllers -. "temporary local compatibility paths" .-> LocalServices

  classDef planned stroke-dasharray: 6 5
  class PhobosBackend,PhobosServices planned
```

## Ownership Rules

- The browser owns interaction mechanics and rendering lifecycles, but not
  campaign data access or backend credentials.
- Trame controllers translate user actions and state changes into application
  operations. They should not depend on SQLite rows, ACA paths, Phobos REST
  objects, or transport-specific query syntax.
- Pure domain logic contains testable workspace, timeline, plot, and
  source-selection policy without Trame dependencies.
- `SeuratApplication` is the facade through which controllers consume backend
  capabilities.
- Backend contracts return normalized Seurat DTOs. Local and Phobos adapters
  implement the same application meaning using different storage and transport.
- The local adapter may use ACA, ADIOS2, SQLite, and ffmpeg internally. Those
  details must not become requirements for the Phobos protocol.
- Phobos should own remote authorization, durable catalog data, media delivery,
  background execution, and artifact persistence.
- Tokens remain on the Python server and must never be serialized into Trame
  state or browser-visible media attributes.

## Current And Planned Capability Boundary

| Capability | Current implementation | Planned direction |
| --- | --- | --- |
| Catalog | Backend-neutral navigation and status | Implement against Phobos campaigns, forays, and variables. |
| Sources | Backend-neutral descriptors, statistics, lookup, and compatibility restriction resolution | Preserve stable source identity and remove the legacy query document after redesign. |
| Query | Python-like parser plus local filter documents | Redesign semantics first, then add a versioned backend-neutral query capability. |
| Stored visualization/media | Controllers still call local data/rendering paths | Add descriptors, explicit timeline metadata, and authorized media transport in Phase 5C. |
| Generated visualization/plugins | Local synchronous generation and plugin paths | Add job, progress, cancellation, error, and result contracts in Phase 5D. |
| Phobos | Design and gap analysis only | Add authenticated adapter after capability contracts are stable. |

The query redesign is intentionally a checkpoint before the planned Query
capability. See [QUERY_REDESIGN.md](QUERY_REDESIGN.md) for the decisions that
must be made before Phase 5B.2 resumes.
