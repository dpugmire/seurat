# Seurat Architecture

This diagram shows the current local application path and the planned Phobos
capability path. Solid arrows represent implemented relationships. Dashed
arrows and nodes labeled "planned" represent future work.

```mermaid
flowchart TB
  subgraph Browser["Browser — Trame Vue 3 client"]
    Components["UI components<br/>toolbar · catalog · grid · dialogs"]
    Widgets["Seurat Vue widgets"]
    Runtimes["Lifecycle-scoped runtimes<br/>timeline · media · plot · interaction · resize"]
    BrowserState["Serialized Trame state"]

    Components --> Widgets
    Widgets --> Runtimes
    Components <--> BrowserState
  end

  subgraph Server["Python Trame application"]
    App["SeuratApp<br/>composition root"]
    UI["UI builder"]
    Controllers["Domain controllers<br/>catalog · sources · grid · visualization<br/>context menu · lifecycle"]
    State["State ownership modules"]
    Models["Pure models<br/>grid · source selection · timeline · plot · plugins"]
    Facade["SeuratApplication<br/>backend-neutral facade"]

    App --> UI
    App --> Controllers
    App --> State
    UI --> Controllers
    Controllers <--> State
    Controllers --> Models
    Controllers --> Facade
  end

  BrowserState <--> State
  UI --> Components

  subgraph Capabilities["Backend capability contracts"]
    Catalog["CatalogBackend<br/>navigation · availability"]
    Sources["SourceBackend<br/>descriptors · statistics · lookup"]
    Query["Query capability<br/>planned after redesign"]
    Media["Visualization/media capability<br/>planned Phase 5C"]
    Jobs["Generated visualization/job capability<br/>planned Phase 5D"]
  end

  Facade --> Catalog
  Facade --> Sources
  Facade -.-> Query
  Facade -.-> Media
  Facade -.-> Jobs

  subgraph Local["Current local ACA implementation"]
    LocalAdapter["LocalCampaignBackend"]
    CampaignDb["CampaignDb<br/>local discovery · reads · rendering"]
    SQLiteAPI["SQLite collection compatibility"]
    Sidecar[("Seurat SQLite sidecar<br/>metadata and cache records")]
    Ingest["Campaign ingestion<br/>schema + visualization associations"]
    ACA[("ACA campaign<br/>SQLite metadata + ADIOS payloads")]
    ADIOS["ADIOS2 payload access"]
    FFmpeg["ffmpeg movie preview"]

    LocalAdapter --> CampaignDb
    CampaignDb --> SQLiteAPI
    SQLiteAPI --> Sidecar
    Ingest --> Sidecar
    Ingest --> ACA
    CampaignDb --> ADIOS
    ADIOS --> ACA
    CampaignDb --> FFmpeg
  end

  Catalog --> LocalAdapter
  Sources --> LocalAdapter
  Query -.-> LocalAdapter
  Media -.-> LocalAdapter
  Jobs -.-> LocalAdapter
  App --> LocalAdapter
  App --> Ingest
  Controllers -->|"current media/generation compatibility"| CampaignDb
  Controllers -->|"current plugin introspection compatibility"| SQLiteAPI

  subgraph Phobos["Future Phobos implementation"]
    PhobosAdapter["PhobosBackend adapter<br/>planned Phase 5E"]
    Auth["Server-side authentication<br/>campaign authorization"]
    APIs["Phobos APIs<br/>campaigns · forays · variables · metadata"]
    ArtifactAPI["Media/artifact delivery<br/>authorized URLs or streams"]
    JobAPI["Background jobs<br/>status · progress · cancellation · results"]
    Persistence[("Phobos persistence and workers")]

    PhobosAdapter --> Auth
    PhobosAdapter --> APIs
    PhobosAdapter --> ArtifactAPI
    PhobosAdapter --> JobAPI
    APIs --> Persistence
    ArtifactAPI --> Persistence
    JobAPI --> Persistence
  end

  Catalog -.-> PhobosAdapter
  Sources -.-> PhobosAdapter
  Query -.-> PhobosAdapter
  Media -.-> PhobosAdapter
  Jobs -.-> PhobosAdapter
```

## Ownership Rules

- The browser owns interaction mechanics and rendering lifecycles, but not
  campaign data access or backend credentials.
- Trame controllers translate user actions and state changes into application
  operations. They should not depend on SQLite rows, ACA paths, Phobos REST
  objects, or transport-specific query syntax.
- Pure models contain testable workspace, timeline, plot, and source-selection
  policy without Trame dependencies.
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
