# Seurat Preference Intelligence v1

Seurat can derive a local, versioned preference profile from immutable
interaction logs. The first policy learns visualization corrections and saved
or final workspace groupings. It uses deterministic weighted evidence and
confidence thresholds; it does not train a neural model or upload data.

## Build and evaluate

Collect several sessions using the same interaction-log directory, then audit
the input:

```bash
python -m seurat.learning.audit /path/to/private/seurat-logs
```

Run chronological walk-forward evaluation. Each session is evaluated using
only earlier sessions, preventing future-data leakage:

```bash
python -m seurat.learning.evaluate /path/to/private/seurat-logs \
  --output evaluation.json
```

Build the profile from all valid events:

```bash
python -m seurat.learning.build_profile \
  /path/to/private/seurat-logs \
  --output ~/.local/share/seurat/preference-profile-v1.json
```

Profile files are written atomically with mode 0600. They are derived artifacts
and never modify the source JSONL files. V1 accepts one pseudonymous user
profile per build; it rejects mixed-user input rather than silently combining
personal preferences. When logging is enabled at runtime, the loaded profile ID
must match the log directory's profile ID.

## Evidence policy

V1 deliberately favors precision over coverage:

- a manual visualization correction is a full-weight preference;
- an explicit manual selection records a win over displayed alternatives;
- removal within 30 seconds is a half-weight negative signal;
- unchanged assignments are not treated as approval;
- workspace groups come from explicit saves and clean-exit final snapshots.

Evidence is aggregated for the exact variable under a normalized query
fingerprint, the exact variable independent of query, a bounded semantic feature
signature, and a global fallback. The fingerprint excludes raw query text,
result counts, and transient query IDs. Laplace smoothing prevents one
interaction from producing extreme confidence. Runtime recommendations require
minimum evidence, multiple sessions, minimum confidence, and a margin over the
next candidate. Otherwise the policy abstains.

The evaluator reports coverage and learned agreement only on explicit choices.
Because corrected decisions are the initial high-confidence labels, the
existing policy's agreement on that subset is expected to be low; it is not a
claim about overall visualization accuracy.

## Runtime modes

Configure a profile separately from interaction logging:

```bash
export SEURAT_PREFERENCE_PROFILE=~/.local/share/seurat/preference-profile-v1.json
export SEURAT_PREFERENCE_MODE=shadow
python app.py campaign.aca
```

Supported modes are:

- `off`: do not use the profile for recommendations; this is the default.
- `shadow`: rank candidates and log confident alternatives without showing or
  applying them.
- `suggest`: show confident alternatives and require explicit confirmation.

`suggest` mode never mutates state merely because a recommendation was shown.
Accepting a visualization suggestion revalidates the active pane, tab, cell,
variable, current visualization, and candidate set, then uses the existing
undoable visualization controller. Dismissal and failure leave the current
visualization unchanged.

When repeated saved/final workspace groups are available, the workspace drawer
offers **Suggest Workspace**. An accepted proposal creates one undoable tab and
populates it through the existing variable-assignment path. Variables that are
unavailable or require unresolved scalar-generation confirmation cause the
proposal to fail without starting the mutation.

Automatic application is intentionally not supported in v1.

## Thresholds

Defaults can be tuned for controlled experiments:

```bash
export SEURAT_PREFERENCE_MIN_EVIDENCE=3
export SEURAT_PREFERENCE_MIN_SESSIONS=2
export SEURAT_PREFERENCE_MIN_CONFIDENCE=0.67
export SEURAT_PREFERENCE_MIN_MARGIN=0.15
```

Reducing thresholds is useful for demonstrations but increases the chance of
overfitting sparse interactions.

## Demonstration

1. Enable interaction logging and use Seurat across several process sessions.
2. Consistently replace a default visualization with a preferred alternative.
3. Save or cleanly exit workspaces containing repeated variable groupings.
4. Run the audit and walk-forward evaluator.
5. Build a profile.
6. Start Seurat in `shadow` mode and collect another session.
7. Inspect the recommendation event counts with the audit command.
8. Restart in `suggest` mode and accept or dismiss displayed recommendations.

Raw queries, assistant prompts, paths, tab titles, array values, media, and
arbitrary plugin settings remain excluded. Profiles and logs stay local unless
the user separately chooses to export them.
