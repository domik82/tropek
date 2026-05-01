# Asset Meta Timeline

## Purpose

The asset meta timeline tracks how an asset's metadata changes over time. External
systems push point-in-time snapshots of key-value metadata, and the timeline module
derives a continuous span-based history that can be queried and visualized.

Use cases: tracking deployment versions, configuration changes, environment labels,
or any structured metadata that evolves over an asset's lifetime.

## Key Concepts

| Concept | What It Is |
|---------|------------|
| **Snapshot** | A point-in-time observation from one source. Contains key-value pairs (values) and/or explicit path closures. Identified by `snapshot_id` (UUID). |
| **Source** | The system that produced a snapshot (e.g., `jenkins`, `k8s-agent`). Each source maintains independent span history per path. |
| **Path** | A hierarchical key with 1--6 segments (e.g., `["app", "frontend", "version"]`). Closing a parent path cascades to all children. |
| **Span** | A continuous period where a path held a specific value. Spans open when a value is first observed and close on value change, explicit closure, or remain open at query time. |
| **Conflict Resolution** | When multiple sources write to the same path, only the most-recently-observed source's spans are kept. Losers are dropped with a warning log. |

## API Endpoints

All endpoints are under the `asset-meta` tag. The router lives in
`api/tropek/modules/asset_meta/router.py`.

### Ingest a snapshot

```
POST /assets/{asset_id}/meta/snapshots
```

Creates a point-in-time metadata snapshot for an asset.

**Request body** (`MetaSnapshotCreate`):
```json
{
  "source": "jenkins",
  "observed_at": "2026-04-30T10:00:00Z",
  "values": [
    { "path": ["app", "version"], "value": "2.1.0" },
    { "path": ["app", "env"], "value": "prod" }
  ],
  "closed": [
    { "path": ["app", "canary"] }
  ]
}
```

Constraints:
- `source`: 1--64 chars, alphanumeric plus `.`, `_`, `-`
- `path`: 1--6 segments, each 1--128 chars
- `value`: max 1024 chars
- At least one of `values` or `closed` must be non-empty
- Duplicate paths within `values` or within `closed` are rejected
- `observed_at` must be timezone-aware

**Response** (201):
```json
{ "snapshot_id": "uuid" }
```

### Query the full timeline

```
GET /assets/{asset_id}/meta/timeline?from={ISO}&to={ISO}
```

Returns the derived timeline for a time window, formatted for vis-timeline rendering.

**Response** (`TimelineResponse`):
```json
{
  "groups": [
    { "id": "[\"app\"]", "content": "app", "nestedGroups": ["[\"app\",\"version\"]"], "showNested": false }
  ],
  "items": [
    {
      "id": "s0",
      "group": "[\"app\",\"version\"]",
      "content": "2.1.0",
      "start": "2026-04-30T10:00:00+00:00",
      "end": "2026-04-30T12:00:00+00:00",
      "type": "range",
      "className": "meta-span",
      "source": "jenkins"
    }
  ]
}
```

### Query the summary

```
GET /assets/{asset_id}/meta/timeline/summary?from={ISO}&to={ISO}
```

Returns only the count of distinct leaf paths with visible spans, without building the
full group hierarchy or item list.

**Response** (`TimelineSummaryResponse`):
```json
{ "itemCount": 12 }
```

### Error responses

| Condition | Status | Exception |
|-----------|--------|-----------|
| Asset not found | 404 | `NotFoundError` |
| `from >= to` | 422 | `DomainValidationError` |
| Schema violation | 422 | Pydantic `ValidationError` |

## Data Model

Three database tables, all with cascade delete from `assets`:

```
asset_meta_snapshots
  id           UUID PK
  asset_id     UUID FK -> assets.id (CASCADE)
  source       TEXT
  observed_at  TIMESTAMPTZ
  created_at   TIMESTAMPTZ (server default)
  indexes:     (asset_id, observed_at), (asset_id, source, observed_at)

asset_meta_values
  id           BIGINT PK auto-increment
  snapshot_id  UUID FK -> asset_meta_snapshots.id (CASCADE)
  path         TEXT[]
  value        TEXT
  unique:      (snapshot_id, path)

asset_meta_closures
  id           BIGINT PK auto-increment
  snapshot_id  UUID FK -> asset_meta_snapshots.id (CASCADE)
  path         TEXT[]
  unique:      (snapshot_id, path)
```

The repository (`AssetMetaRepository` in `repositories.py`) loads snapshots with three
separate SQL queries (snapshots, values, closures) and groups them in Python. Snapshots
are ordered by `observed_at ASC, id ASC` for deterministic processing.

## Timeline Derivation Pipeline

The timeline is derived on every read through a pure, zero-I/O pipeline. All pipeline
code lives in `api/tropek/modules/asset_meta/timeline/`. The orchestrator
(`build_timeline_response` in `orchestrator.py`) chains five stages:

```
Snapshots  -->  Stage 1: Derivation  -->  Stage 2: Conflict Resolution  -->  Stage 3: Clipping
                                                                                  |
                                          Stage 5: Item Emission  <--  Stage 4: Tree Building
                                                      |                        |
                                                      v                        v
                                                   { items: [...],  groups: [...] }
```

Type flow:

```
list[SnapshotWithEntries]
  -> derive_raw_spans       -> list[RawSpan]
  -> resolve_multi_source_conflicts -> list[RawSpan]
  -> clip_spans             -> list[ClippedSpan]
  -> build_groups_wire      -> list[dict]    (groups)
  -> build_items_wire       -> list[dict]    (items)
```

### Stage 1: Derivation

**File:** `timeline/derivation.py`
**Entry point:** `derive_raw_spans(snapshots) -> list[RawSpan]`

Walks snapshots in chronological order and builds spans by tracking open `(source, path)`
pairs. For each snapshot:

1. **Closures run first** -- `close_cascade` closes the target path and all descendant
   paths for that source. This ordering enables close-and-reopen semantics: a snapshot
   can close a path and set a new value in the same observation.
2. **Values run second** -- `apply_value` opens a new span if none exists, is a no-op if
   the value is unchanged, or closes the old span (with `end_reason='value_change'`) and
   opens a new one if the value changed.

After all snapshots, `finalize_open_spans` emits remaining open spans with `end=None`
and `end_reason='open'`.

Key functions:

| Function | Purpose |
|----------|---------|
| `derive_raw_spans` | Top-level entry point, iterates snapshots |
| `apply_snapshot` | Applies one snapshot (closures then values) |
| `apply_value` | Handles one value observation (open/no-op/change) |
| `close_cascade` | Closes a path and all descendants for a source |
| `finalize_open_spans` | Emits still-open spans after all snapshots |
| `is_prefix` | Checks if one path tuple is a prefix of another |

### Stage 2: Conflict Resolution

**File:** `timeline/conflict_resolution.py`
**Entry point:** `resolve_multi_source_conflicts(spans, asset_id, logger) -> list[RawSpan]`

When multiple sources write to the same path, only one source's spans survive:

1. Group spans by path tuple
2. Single-source paths pass through unchanged
3. Multi-source paths: pick the source with the most recent observation timestamp.
   Open spans (no end) use `datetime.max` as a sentinel, so currently-open data always
   wins. Alphabetical source name is the tiebreaker.
4. All spans from losing sources are dropped; a structured warning is logged

Key functions:

| Function | Purpose |
|----------|---------|
| `resolve_multi_source_conflicts` | Top-level entry point |
| `group_spans_by_path` | Buckets spans by path tuple |
| `compute_latest_observation_per_source` | Finds latest timestamp per source |
| `pick_winning_source` | Most-recent-wins with alphabetical tiebreak |
| `log_source_conflict` | Emits structured warning log |

### Stage 3: Clipping

**File:** `timeline/clipping.py`
**Entry point:** `clip_spans(spans, window_from, window_to) -> list[ClippedSpan]`

Clips raw spans to the query window `[window_from, window_to]`:

- Spans entirely outside the window are dropped
- Start and end are clamped to window bounds
- Open spans (`end=None`) use `window_to` as their effective end
- Each span is annotated with CSS classes for rendering

CSS class vocabulary:

| Class | Condition |
|-------|-----------|
| `meta-span` | Always present (base class) |
| `meta-span-clipped-left` | Span started before `window_from` |
| `meta-span-open` | Span has no end (`end_reason='open'`) |
| `meta-span-clipped-right` | Span ends after `window_to` |
| `meta-span-closed` | Span was explicitly terminated (`end_reason='closed'`) |

Multiple classes can be present simultaneously.

### Stage 4: Tree Building

**File:** `timeline/tree_builder.py`
**Entry point:** `build_groups_wire(clipped_spans) -> list[dict]`

Builds the vis-timeline group hierarchy:

1. Collect distinct path tuples from clipped spans
2. Expand with synthetic ancestors -- if only leaf `("a","b","c")` exists, add
   `("a",)` and `("a","b")` as parent groups
3. Compute parent-to-children map
4. Sort deterministically: depth ascending (roots first), then lexicographic
5. Emit group entries with `id` (JSON-encoded path array), `content` (last path segment),
   and optional `nestedGroups`/`showNested` for parent nodes

Groups are collapsed by default (`showNested: false`).

### Stage 5: Item Emission

**File:** `timeline/item_emitter.py`
**Entry point:** `build_items_wire(spans) -> list[dict]`

One-to-one transform from `ClippedSpan` to vis-timeline item dict. Each item has:
`id` (`s0`, `s1`, ...), `group` (JSON-encoded path), `content` (the value),
ISO-formatted `start`/`end`, `type: 'range'`, `className`, and `source`.

## Pipeline Data Types

All types are frozen dataclasses defined in `timeline/types.py`:

| Type | Fields | Role |
|------|--------|------|
| `SnapshotWithEntries` | `source`, `observed_at`, `values`, `closures` | Bridge between repository rows and the pipeline |
| `RawSpan` | `source`, `path`, `value`, `start`, `end`, `end_reason` | Output of derivation. `end` is `None` for open spans. `end_reason` is `'value_change'`, `'closed'`, or `'open'` |
| `ClippedSpan` | `source`, `path`, `value`, `start`, `end`, `className` | Window-clipped span ready for rendering. `end` is always set |
| `OpenSpan` | `value`, `span_start` | Internal to derivation -- tracks a span not yet closed |
| `OpenSpanMap` | Type alias: `dict[tuple[str, tuple[str, ...]], OpenSpan]` | Mutable accumulator keyed by `(source, path_tuple)`, local to the derivation walk |

## Source Layout

```
api/tropek/modules/asset_meta/
  __init__.py
  schemas.py              # Pydantic request/response schemas
  repositories.py         # Data access layer (AssetMetaRepository)
  service.py              # Service layer (create_meta_snapshot, get_timeline, get_timeline_summary)
  router.py               # FastAPI routes (POST ingest, GET timeline, GET summary)
  timeline/
    __init__.py            # Re-exports SnapshotWithEntries, build_timeline_response, count_distinct_leaf_paths
    types.py               # Frozen dataclasses: RawSpan, ClippedSpan, OpenSpan, SnapshotWithEntries
    orchestrator.py        # build_timeline_response -- chains all five stages
    derivation.py          # Span derivation: snapshot walk, open/close/change logic
    conflict_resolution.py # Multi-source conflict resolution (most-recent-wins)
    clipping.py            # Window clipping and CSS class annotation
    tree_builder.py        # vis-timeline group hierarchy with synthetic ancestors
    item_emitter.py        # ClippedSpan -> vis-timeline item dict
    summary.py             # count_distinct_leaf_paths
```

## Design Decisions

**Pure pipeline.** The entire `timeline/` package has zero I/O. All five stages are
pure functions, independently testable without database or network. The only side effect
is the conflict resolution warning log.

**Closures before values.** Within a single snapshot, closures are processed before
values. This enables close-and-reopen: a snapshot can close a path and immediately set a
new value, producing two distinct spans.

**Hierarchical closure cascade.** Closing path `["app"]` also closes `["app", "frontend"]`
and any other descendant. This is implemented via `is_prefix` matching in `close_cascade`.

**Source isolation during derivation.** Each `(source, path)` pair has independent span
history. Source A closing `["app"]` does not affect source B. Cross-source conflicts are
resolved in a separate stage after derivation completes.

**Lossy conflict resolution.** When multiple sources write to the same path, losing
sources' spans are dropped entirely. The warning log is the only record. There is no
mechanism to preserve or merge multi-source history.

**vis-timeline wire format.** The output is tightly coupled to the vis-timeline JS
library's expected shape: group IDs are JSON-encoded path arrays, items use `className`
(camelCase), groups have `nestedGroups`/`showNested`. This coupling is intentional for
the purpose-built UI.
