# Asset Meta Timeline — Phase 1 Design

**Status:** Draft
**Date:** 2026-04-16
**Author:** Dominik Jeziorski (with Claude)
**Supersedes:** `docs/meta-gantt/asset_version_gantt_spec.docx` (v0.1, pre-specification)

---

## 1. Purpose

Performance and quality-gate evaluations in TROPEK are run repeatedly against the same
physical or virtual assets (VMs, services, laptops, endpoints). The interpretation of
an evaluation's result depends on the **state of the asset at the moment the eval ran**
— what software was installed, at which versions, with which feature flags toggled, at
which hardware configuration.

Today, there is no structured way to see how an asset's state changed over time alongside
its evaluation history. Users work around this by typing free-text notes into evaluation
annotations, which:

- Cannot be read at a glance — notes are unstructured text.
- Do not form a visual timeline — you cannot see "this version spanned from A to B".
- Do not connect an eval result to the state that produced it.
- Rot quickly as the asset evolves.

This feature introduces a **collapsible Gantt-style section inside the evaluation detail
view** that shows the asset's meta-state history as a set of horizontal timeline rows.
When you look at an evaluation, you see a vertical marker at that eval's timestamp
crossing every meta row — and the value of each row at the marker is the exact state
of the asset at the moment the eval ran.

The feature is read-only. All data arrives via a dedicated ingestion endpoint pushed by
external systems (CI/CD pipelines, scheduled workers, manual `curl` calls). The UI never
writes meta data.

---

## 2. Scope

### In scope (Phase 1)

- Storing point-in-time snapshots of asset meta data, source-tagged for scoped ownership.
- Deriving timeline spans at query time from those snapshots (never materialized).
- A read endpoint that returns data **directly in vis-timeline's consumer format** so
  the UI does zero domain translation.
- A **default-collapsed single-row strip** placed between the heatmap and the first
  table in the evaluation detail page. The strip shows a lightweight "N items
  tracked" summary and expands on click to reveal the full vis-timeline with the
  current evaluation pinned as a non-draggable vertical marker. The collapsed state
  is the primary state — the timeline is an investigation tool, not a routine
  artifact, and the eval detail page's normal flow (heatmap → scores → tables)
  stays intact until a user actively wants to investigate changes.
- Hierarchical meta via path-based keys (app → plugin-package → plugin → ... up to 6
  levels deep), rendered using vis-timeline's native `nestedGroups` + `showNested`.
- Explicit closure semantics — a key is only "uninstalled" when the owning source
  explicitly closes it. Missing data means "no news", not "removed". Cascading
  closures: closing a parent path closes all descendants in the same source.
- Read-only rendering — no drag, no resize, no edit, no selection. The widget is
  locked down on three orthogonal knobs (`editable: false`, `selectable: false`,
  `moveable: true` for pan only).

### Out of scope (Phase 1, deferred to Phase 2+)

- **Per-run feature flags / one-shot overrides.** The "this one eval toggled feature X
  on" case. Persistent flag state is in scope; per-run context is not. Deferred to
  Phase 2 as eval-scoped pins rendered on the focus-eval marker column.
- **Staleness hints on trailing edges.** "last confirmed 47 days ago" visual treatment
  when a source hasn't been heard from. Deferred — rendering heuristic only, does not
  affect storage.
- **Multi-asset comparison, diff views, export** (CSV/PNG). Deferred.
- **Agent / collector tooling.** We provide the endpoint; whoever wants to push to it
  builds their own collector (CI/CD hooks, crons, `curl`). No agent is part of this
  feature.
- **Semver parsing / structured versions.** Values are stored as opaque strings. No
  "patch vs minor vs major" highlighting, no range queries on parsed semver.
- **Writes from the UI.** Permanent non-goal. Corrections are pushed through ingestion
  by the source that owns the key, same path as initial creation.
- **User-controlled zoom / range selector / date pickers** in the UI toolbar. Phase 1
  uses a fixed default window (`focus_eval.period_end ± 30d` / `+ 7d`). Users can pan
  and wheel-zoom within that window.
- **Remembered expand/collapse state across sessions.** All parents collapse by
  default on every mount. Phase 2 may persist last state.
- **Most-recent-source-wins conflict UI** when two sources push the same path at
  overlapping times. Rare, flagged to implementers as a data warning to log; not a
  visual treatment in Phase 1.

---

## 3. Glossary

| Term | Definition |
|---|---|
| **Asset** | A physical machine, virtual endpoint, or logical service on which evaluations run. Already an existing concept in TROPEK; unchanged. |
| **Evaluation run** | An existing `EvaluationRun` row. The "focus eval" is the one currently being viewed in the detail page. |
| **Meta key (path)** | An ordered list of strings identifying a thing we track over time. Examples: `["app-A"]`, `["app-A", "plugin-pkg-1", "plugin-alpha"]`, `["cpu-cores"]`, `["feature-flags", "enable-new-x"]`. The path IS the identity. Two plugins with the same leaf name under different parents are distinct paths and render as distinct rows. |
| **Meta value** | An opaque string associated with a path at a point in time. `"2.3.0"`, `"Enterprise"`, `"true"`, `"4"`. No parsing. |
| **Source** | A stable short string identifying the system pushing meta data. Examples: `"cicd"`, `"os-agent"`, `"manual"`, `"nightly"`. Used for ownership scoping: silence from source X only affects keys previously pushed by source X. |
| **Snapshot** | One push from one source at one `observed_at` timestamp. Contains any number of `(path, value)` entries under `values` and any number of `path` entries under `closed`. |
| **Span** | A contiguous time range during which a given `(source, path)` had the same `value`. Derived from consecutive snapshots at query time. Never materialized in storage. |
| **Closure** | An explicit "this key is no longer present" event, pushed as `{path}` in a snapshot's `closed` list. Cascading: closing a path closes all currently-open descendants in the same source. |

---

## 4. Data model

### 4.1 Tables

Three new tables. All are append-only at the application layer (rows are never updated;
corrections are expressed as new snapshots).

```sql
-- One row per push. The "frame" of a meta observation.
CREATE TABLE asset_meta_snapshots (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id    UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    source      TEXT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_asset_meta_snapshots_asset_observed
    ON asset_meta_snapshots (asset_id, observed_at);

CREATE INDEX idx_asset_meta_snapshots_asset_source_observed
    ON asset_meta_snapshots (asset_id, source, observed_at);

-- Per-entry values carried by a snapshot.
CREATE TABLE asset_meta_values (
    id           BIGSERIAL PRIMARY KEY,
    snapshot_id  UUID NOT NULL REFERENCES asset_meta_snapshots(id) ON DELETE CASCADE,
    path         TEXT[] NOT NULL,
    value        TEXT NOT NULL,
    UNIQUE (snapshot_id, path)
);

CREATE INDEX idx_asset_meta_values_snapshot ON asset_meta_values (snapshot_id);

-- Explicit closure markers carried by a snapshot.
-- A closure row represents "at this snapshot's observed_at, close the span for this path
-- (and cascade to descendants) for the snapshot's source".
CREATE TABLE asset_meta_closures (
    id           BIGSERIAL PRIMARY KEY,
    snapshot_id  UUID NOT NULL REFERENCES asset_meta_snapshots(id) ON DELETE CASCADE,
    path         TEXT[] NOT NULL,
    UNIQUE (snapshot_id, path)
);

CREATE INDEX idx_asset_meta_closures_snapshot ON asset_meta_closures (snapshot_id);
```

### 4.2 Why three tables (and not two)

The original design considered folding closures into `asset_meta_values` with a sentinel
value (e.g. `value = NULL` or `value = ''` meaning "closed"). That is rejected on the
"no in-band signaling" principle: mixing two kinds of facts (present values, closure
events) into one table using a magic value invites silent corruption (`NULL` vs empty
string vs explicit-empty-string-that-was-a-real-value). A dedicated `asset_meta_closures`
table makes the intent explicit in the schema itself and costs nothing at query time.

### 4.3 Why `TEXT[]` for paths

PostgreSQL's native array type supports all operators we need (`=`, `@>`, slicing in app
code) and maps directly to Python `list[str]` via asyncpg. Using arrays avoids delimiter
escaping (a plugin name can contain `/`, `.`, `:`, spaces — anything). Max depth is
enforced at the application layer (see §5.2 validation rules), not at the schema.

### 4.4 Path canonicalization

Paths are stored verbatim as received. The canonical form is the `TEXT[]` with
components in order. The wire-format group id used by vis-timeline is a JSON-encoded
array (see §7.2) — that is a presentation concern, not a storage concern.

No trimming, no case normalization, no Unicode normalization. Whatever the client pushes
is exactly what is stored and exactly what comes back.

### 4.5 Retention and cleanup

Phase 1 has no automatic retention. Rows are kept indefinitely. At expected volumes
(single-digit snapshots per asset per day × tens of entries per snapshot) a year of data
is well under a million rows per asset cluster. If retention becomes necessary, a
simple "delete snapshots older than N days" job is trivial to add; the cascade will
clean up values and closures automatically.

---

## 5. Ingestion API

### 5.1 Endpoint

```
POST /assets/{asset_id}/meta/snapshots
Content-Type: application/json
Authorization: <existing TROPEK API key scheme>
```

**Request body:**

```json
{
  "source": "cicd",
  "observed_at": "2026-04-16T14:32:00Z",
  "values": [
    { "path": ["app-A"],                                 "value": "2.3.0" },
    { "path": ["app-A", "plugin-pkg-1"],                 "value": "1.0.2" },
    { "path": ["app-A", "plugin-pkg-1", "plugin-alpha"], "value": "0.9.1" },
    { "path": ["cpu-cores"],                             "value": "4" },
    { "path": ["feature-flags", "enable-new-x"],         "value": "true" }
  ],
  "closed": [
    { "path": ["legacy-plugin"] }
  ]
}
```

**Response (201 Created):**

```json
{ "snapshot_id": "9c4e5a40-3f2d-4e8f-8a2b-1e5c7d2f4a91" }
```

**Valid payload shapes.** A snapshot does not need to contain both `values` and
`closed`. All three of the following are legal:

1. **`values`-only** — the common case. The agent is reporting current state; nothing
   has been uninstalled since the last push. `closed` is omitted or `[]`.
2. **`closed`-only** — the "I just noticed something disappeared, nothing else
   changed" case. Useful when an agent's diff between two collection cycles is
   purely "one thing vanished". Example:

   ```json
   {
     "source": "cicd",
     "observed_at": "2026-04-16T14:32:00Z",
     "closed": [
       { "path": ["legacy-plugin"] },
       { "path": ["app-A", "plugin-pkg-1", "plugin-beta"] }
     ]
   }
   ```

   Semantics: terminate the currently-open spans for `legacy-plugin` and
   `plugin-beta` (both as owned by the `cicd` source) at `2026-04-16T14:32:00Z`.
   No new spans are opened. If either path has no open span from `cicd` at that
   moment, the closure is a no-op for that path (not an error) — closures are
   idempotent-safe.

3. **Both together** — values + closures in one push. The close-and-reopen special
   case (§5.2 rule 3) uses this, but the general form also works: some things
   terminated, other things observed at their current value, all in one transaction.

A snapshot with **both** `values` and `closed` empty is rejected — see §5.2 rule 4.

### 5.2 Field types and validation rules

| Field | Type | Required | Validation |
|---|---|---|---|
| `source` | `str` | Yes | 1–64 characters; `^[a-zA-Z0-9._-]+$`; case-sensitive. |
| `observed_at` | ISO-8601 datetime with timezone | Yes | Must be a valid ISO-8601 datetime **with timezone offset** (naive datetimes rejected as 400). Normalized to UTC via `astimezone(UTC)` on receipt so all downstream code compares in UTC. No upper or lower bound — backfills of historical data and slightly-skewed-clock agents are both legitimate callers. A call pushing `observed_at` in the year 2000 or 2100 is technically legal; the data just appears in the timeline when queried with a matching window. |
| `values` | `list[MetaValue]` | No | Default `[]`. Up to 10,000 entries per snapshot (hard limit). |
| `closed` | `list[MetaClosure]` | No | Default `[]`. Up to 1,000 entries per snapshot. |
| `values[].path` | `list[str]` | Yes | 1–6 entries (inclusive); each entry 1–128 characters; entries cannot be empty; Unicode allowed. |
| `values[].value` | `str` | Yes | 0–1024 characters (empty string is allowed — it is a valid value, distinct from "closed"). |
| `closed[].path` | `list[str]` | Yes | Same rules as `values[].path`. |

**Structural validation:**

1. Within a single request, no two `values[]` entries may have the same `path`.
2. Within a single request, no two `closed[]` entries may have the same `path`.
3. Within a single request, a path may appear in **both** `values[]` and `closed[]`.
   Semantics in this edge case: the closure applies first (terminates any pre-existing
   open span for (source, path) and its descendants), then the value in `values[]`
   opens a new span starting at `observed_at`. This lets an agent express
   "close-and-reopen" in one push without ambiguity. Rare but legal.
4. Either `values` or `closed` must be non-empty. An empty push is rejected with 400
   (a snapshot with no content is meaningless and usually a bug).

**Validation errors return 400 Bad Request** with an error body naming the offending
field and the rule violated. No partial writes — validation is a single pre-flight
pass before the DB transaction.

### 5.3 Write semantics

Writes are purely additive. One `POST` creates exactly one `asset_meta_snapshots` row,
`len(values)` `asset_meta_values` rows, and `len(closed)` `asset_meta_closures` rows, all
in a single transaction. Nothing is read beforehand; no existing rows are updated or
deleted. Derivation is deferred to read time.

### 5.4 Idempotency

Not guaranteed in Phase 1. A client that pushes the same payload twice creates two
snapshots with the same `observed_at` and the same content. The derivation algorithm
will collapse duplicates naturally (two identical consecutive observations form one
span), so this is harmless in practice — but it is a trap if a caller relies on HTTP
semantics for idempotency. A Phase 2 improvement is to add a client-supplied
`Idempotency-Key` header that short-circuits on repeat; the server would store it on
the snapshot and reject duplicates. Noted as a non-blocker.

### 5.5 Source naming conventions (advisory)

Sources are free-form strings but we recommend:

- `cicd-<pipeline-name>` for CI/CD hooks
- `agent-<role>` for scheduled collectors (`agent-os`, `agent-docker`)
- `manual-<user>` or `manual` for ad-hoc human pushes
- Avoid generic `default` — it makes debugging harder when multiple systems share it.

These are advisory; the server does not enforce them.

---

## 6. Read API

### 6.1 Endpoint

```
GET /assets/{asset_id}/meta/timeline?from={iso}&to={iso}
Authorization: <existing TROPEK API key scheme>
```

### 6.2 Query parameters

| Param | Type | Required | Description |
|---|---|---|---|
| `from` | ISO-8601 datetime | Yes | Left edge of the visible window, inclusive. |
| `to` | ISO-8601 datetime | Yes | Right edge of the visible window, inclusive. Must be > `from`. |

The endpoint does **not** take a `focus_eval` parameter. The UI already has the focused
evaluation object loaded and will set the vertical marker locally via
`timeline.addCustomTime(focusEval.periodEnd, "focus")`. Keeping this out of the server
contract reduces coupling and means the backend has one less piece of state to manage.

### 6.3 Response body (success, 200 OK)

```json
{
  "groups": [
    {
      "id": "[\"app-A\"]",
      "content": "app-A",
      "nestedGroups": [
        "[\"app-A\",\"plugin-gamma\"]",
        "[\"app-A\",\"plugin-pkg-1\"]"
      ],
      "showNested": false
    },
    {
      "id": "[\"app-A\",\"plugin-gamma\"]",
      "content": "plugin-gamma"
    },
    {
      "id": "[\"app-A\",\"plugin-pkg-1\"]",
      "content": "plugin-pkg-1",
      "nestedGroups": [
        "[\"app-A\",\"plugin-pkg-1\",\"plugin-alpha\"]",
        "[\"app-A\",\"plugin-pkg-1\",\"plugin-beta\"]"
      ],
      "showNested": false
    },
    {
      "id": "[\"app-A\",\"plugin-pkg-1\",\"plugin-alpha\"]",
      "content": "plugin-alpha"
    },
    {
      "id": "[\"app-A\",\"plugin-pkg-1\",\"plugin-beta\"]",
      "content": "plugin-beta"
    },
    {
      "id": "[\"cpu-cores\"]",
      "content": "cpu-cores"
    },
    {
      "id": "[\"feature-flags\"]",
      "content": "feature-flags",
      "nestedGroups": [
        "[\"feature-flags\",\"enable-new-x\"]"
      ],
      "showNested": false
    },
    {
      "id": "[\"feature-flags\",\"enable-new-x\"]",
      "content": "enable-new-x"
    }
  ],
  "items": [
    {
      "id": "s0",
      "group": "[\"app-A\"]",
      "content": "2.3.0",
      "start": "2026-03-17T00:00:00Z",
      "end":   "2026-04-16T14:32:00Z",
      "type": "range",
      "className": "meta-span",
      "source": "cicd"
    },
    {
      "id": "s1",
      "group": "[\"app-A\",\"plugin-pkg-1\",\"plugin-alpha\"]",
      "content": "0.9.1",
      "start": "2026-03-17T00:00:00Z",
      "end":   "2026-04-16T14:32:00Z",
      "type": "range",
      "className": "meta-span meta-span-clipped-left",
      "source": "cicd"
    },
    {
      "id": "s2",
      "group": "[\"cpu-cores\"]",
      "content": "4",
      "start": "2026-03-17T00:00:00Z",
      "end":   "2026-04-23T00:00:00Z",
      "type": "range",
      "className": "meta-span meta-span-open",
      "source": "agent-os"
    }
  ]
}
```

### 6.4 Wire format — exact shape

The response is **already in vis-timeline's consumer format**. The UI passes `groups` and
`items` almost directly to `new vis.Timeline(container, items, groups, options)` — the
only client-side transformation is converting ISO date strings to `Date` objects for
`start`/`end`.

#### 6.4.1 Group object

| Field | Type | Present on |
|---|---|---|
| `id` | string | Every group. JSON-encoded path array. Stable and uniquely invertible to the path. Used by vis-timeline internally for item→group matching; not user-visible. |
| `content` | string | Every group. The leaf component of the path (`path[-1]`). Used as the row label. vis-timeline indents by nesting level automatically. |
| `nestedGroups` | `list[str]` | Present only on groups that have at least one child in the emitted tree. Lists the immediate-child group ids (not transitive). |
| `showNested` | `bool` | Present only on groups with `nestedGroups`. Always `false` in Phase 1 (default collapsed). |

#### 6.4.2 Item object

| Field | Type | Description |
|---|---|---|
| `id` | string | Per-span identifier unique within one response. Format: `s<index>` where index is the span's position in the emitted list (see §7.5). Stability across requests is not guaranteed and not required — vis-timeline only needs uniqueness within a single render. |
| `group` | string | The JSON-encoded path of the span. Matches a `groups[].id`. |
| `content` | string | The span's `value`, rendered inside the bar. |
| `start` | ISO-8601 datetime string | Left edge. Always present. Clipped to `from` if the span started earlier. |
| `end` | ISO-8601 datetime string | Right edge. Always present. See §7.3 for clipping rules — never `null` on the wire. |
| `type` | `"range"` | Always `"range"` in Phase 1. |
| `className` | string | Space-separated CSS classes. See §7.3 class vocabulary for the meaning of each class and §9.4 for the CSS that consumes them. |
| `source` | string | The source identifier that owns this span. Echoed through from the snapshot that started the span. The UI tooltip template (see §9.5) displays it; no other UI code reads it. Not used by vis-timeline directly — it is an extra field that vis-timeline passes through unchanged on item objects, available inside `tooltip.template` via `item.source`. |

**Note on the `title` field.** The vis-timeline `Item` shape supports an optional `title`
property that it renders as a plain-text native tooltip on hover. We deliberately **do
not** populate it — the UI overrides vis-timeline's default tooltip with a richer
custom `tooltip.template` (see §9.5) that reads from `item.content`, `item.start`,
`item.end`, `item.className`, `item.source`, and `item.group`. Populating `title`
would cause two tooltips to appear, which is visually confusing and cannot be styled
consistently.

### 6.5 Response for an empty asset

If the asset has no meta data in the window, the server returns:

```json
{ "groups": [], "items": [] }
```

The UI renders the collapsible section in its "nothing to show" state — the section
title is visible but expanding it shows a placeholder ("No meta data recorded for this
asset yet. See docs → Meta Ingestion to start pushing.").

### 6.6 Error responses

- **400 Bad Request** — `from` and `to` not both provided, or `from >= to`, or malformed
  datetimes.
- **404 Not Found** — `asset_id` does not exist.
- **500 Internal Server Error** — derivation error (log with full snapshot dump).

### 6.7 Summary endpoint (for the collapsed strip)

The UI's default-collapsed strip (see §9.2) shows a lightweight "N items tracked"
count without issuing the full timeline query. This is served by a second endpoint:

```
GET /assets/{asset_id}/meta/timeline/summary?from={iso}&to={iso}
```

**Query parameters:** identical to `GET /assets/{asset_id}/meta/timeline` — same
`from` / `to` semantics so the count reflects exactly the same window that would be
rendered on expand.

**Response (200 OK):**

```json
{ "itemCount": 7 }
```

Where `itemCount` is the number of **distinct leaf paths** (groups that have at
least one span in the window — synthetic intermediate ancestors do not count). For
example, if the window has values for `["app-A"]`, `["app-A", "plugin-alpha"]`, and
`["cpu-cores"]`, the count is 3 (not 4; `["app-A"]` is a leaf only if it has its
own value, and the synthetic parent if any does not add to the count).

**Error responses:** identical to §6.6 — 400 / 404 / 500.

**Implementation note.** The summary endpoint is a **cheap specialization** of the
full read path: it reuses `derive_raw_spans` + `resolve_multi_source_conflicts` +
`clip_spans` exactly as §7 describes, then counts `len({tuple(s.path) for s in
clipped})` instead of running tree building and item emission. The savings come from
avoiding JSON serialization of the full response, not from a different algorithm.

A future optimization (not Phase 1) could answer this from an index without walking
snapshots — e.g. a materialized "latest non-null value per (asset, path)" view —
but the current implementation is a ~5-line function and fast enough for Phase 1
data volumes.

```python
# service.py — additional method

async def get_timeline_summary(
    session: AsyncSession,
    asset_id: UUID,
    window_from: datetime,
    window_to: datetime,
) -> TimelineSummaryResponse:
    await _ensure_asset_exists(session, asset_id)
    snapshots = await meta_repo.load_snapshots_for_derivation(
        session, asset_id=asset_id, until=window_to,
    )
    raw_spans = derive_raw_spans(snapshots)
    resolved = resolve_multi_source_conflicts(raw_spans, asset_id, logger)
    clipped = clip_spans(resolved, window_from, window_to)
    item_count = count_distinct_leaf_paths(clipped)
    return TimelineSummaryResponse(item_count=item_count)


def count_distinct_leaf_paths(spans: list[ClippedSpan]) -> int:
    """Count distinct paths present in the clipped spans.

    Pure function. Phase 1 treats every span's path as a "leaf" — synthetic
    ancestors are a rendering concept that only exist after tree_builder runs.
    """
    return len({tuple(s.path) for s in spans})
```

`count_distinct_leaf_paths` gets its own one-line test (single fixture, one
assertion). Reusing the existing pure functions means there is no second code path
to keep in sync with the full endpoint.

---

## 7. Server-side algorithms

**Design principles for this section.** Every algorithmic function described below is:

- **Pure** (except where marked `async` for DB I/O). Derivation, conflict resolution,
  clipping, tree building, and item emission are all zero-I/O: they take data in, return
  data out, and have no side effects beyond an optional log warning.
- **Single-purpose.** Each function does exactly one thing. The top-level orchestrator
  `build_timeline_response` is a 5-line composition of the stages; it does no real work
  itself.
- **Independently unit-testable.** Each function can be exercised in isolation with a
  small fixture — no DB, no network, no mocks beyond `logger`. §10.1 lists a focused
  test case per function.
- **DRY across read and write paths.** The `_ensure_asset_exists` helper is shared by
  both the ingest and read services (§8.3). The `encode_path_as_group_id` helper is the
  single point of truth for path → vis-timeline group-id encoding.

The full function decomposition is:

```
# derivation.py  (pure, zero I/O)
derive_raw_spans(snapshots)                             -> list[RawSpan]
  apply_snapshot(open_spans, snapshot, emitted)         -> None
    apply_value(open_spans, source, path, value, t, emitted)  -> None
    close_cascade(open_spans, source, ancestor, t, emitted)   -> None
      is_prefix(prefix, full)                           -> bool
  finalize_open_spans(open_spans, emitted)              -> None

# conflict_resolution.py  (pure, logger-only side effect)
resolve_multi_source_conflicts(spans, asset_id, logger) -> list[RawSpan]
  group_spans_by_path(spans)                            -> dict[path, list[RawSpan]]
  compute_latest_observation_per_source(spans)          -> dict[source, datetime]
  pick_winning_source(sources_latest)                   -> str
  log_source_conflict(logger, asset_id, path, sources, winner)  -> None

# clipping.py  (pure)
clip_spans(spans, window_from, window_to)               -> list[ClippedSpan]
  clip_one_span(span, window_from, window_to)           -> ClippedSpan | None
    compute_span_classes(span, window_from, window_to, clipped_start, clipped_end)  -> list[str]

# tree_builder.py  (pure)
build_groups_wire(clipped_spans)                        -> list[dict]
  collect_distinct_paths(spans)                         -> set[tuple]
  expand_with_synthetic_ancestors(paths)                -> set[tuple]
  compute_children_map(paths)                           -> dict[path, list[path]]
  sort_groups_deterministically(paths)                  -> list[tuple]
  build_group_entry(path, children_map)                 -> dict
  encode_path_as_group_id(path)                         -> str

# item_emitter.py  (pure)
build_items_wire(spans)                                 -> list[dict]
  item_from_span(span, index)                           -> dict

# orchestrator.py  (pure)
build_timeline_response(asset_id, snapshots, window_from, window_to, logger)  -> dict
```

Each bullet in the list above is a separate named function with a single responsibility.
Sub-functions are called only by their listed parent; cross-module calls go through the
top-level public function of each module (e.g., `tree_builder.build_groups_wire` is
public; `compute_children_map` is a private module helper).

### 7.1 Span derivation

Given: `asset_id`, window `[from, to]`.

**Step 1 — fetch.** Load all `asset_meta_snapshots` for the asset with `observed_at <= to`
(we need snapshots before `from` to know the state at the left edge), joined with their
`asset_meta_values` and `asset_meta_closures` rows. Order by `observed_at ASC`, tie-break
on `id ASC` for determinism.

In pseudocode:

```
snapshots = SELECT s.*, v.path AS v_path, v.value, c.path AS c_path
            FROM asset_meta_snapshots s
            LEFT JOIN asset_meta_values v ON v.snapshot_id = s.id
            LEFT JOIN asset_meta_closures c ON c.snapshot_id = s.id
            WHERE s.asset_id = :asset_id
              AND s.observed_at <= :to
            ORDER BY s.observed_at ASC, s.id ASC
```

Group the flat join result into `(snapshot, values_list, closures_list)` tuples in
application code.

**Step 2 — walk and emit (small, composable functions).**

```python
# derivation.py

from collections.abc import Iterable

OpenSpanMap = dict[tuple[str, tuple[str, ...]], "OpenSpan"]


@dataclass(frozen=True)
class OpenSpan:
    value: str
    span_start: datetime


def derive_raw_spans(snapshots: Iterable[SnapshotWithEntries]) -> list[RawSpan]:
    """Top-level entry point. Walks snapshots in order and emits raw spans.

    Pure function. Zero I/O. The caller (`build_timeline_response`) owns snapshot
    loading.
    """
    open_spans: OpenSpanMap = {}
    emitted: list[RawSpan] = []
    for snapshot in snapshots:
        apply_snapshot(open_spans, snapshot, emitted)
    finalize_open_spans(open_spans, emitted)
    return emitted


def apply_snapshot(
    open_spans: OpenSpanMap,
    snapshot: SnapshotWithEntries,
    emitted: list[RawSpan],
) -> None:
    """Apply one snapshot to the in-progress state.

    Closures run BEFORE values so that close-and-reopen in the same push is
    deterministic (old span ends, new span starts, both at observed_at).
    """
    for closure_path in snapshot.closures:
        close_cascade(
            open_spans=open_spans,
            source=snapshot.source,
            ancestor=tuple(closure_path),
            closed_at=snapshot.observed_at,
            emitted=emitted,
        )
    for path, value in snapshot.values:
        apply_value(
            open_spans=open_spans,
            source=snapshot.source,
            path=tuple(path),
            value=value,
            observed_at=snapshot.observed_at,
            emitted=emitted,
        )


def apply_value(
    open_spans: OpenSpanMap,
    source: str,
    path: tuple[str, ...],
    value: str,
    observed_at: datetime,
    emitted: list[RawSpan],
) -> None:
    """Record one observation of (source, path) = value at observed_at.

    - If no span is currently open for (source, path), open one.
    - If an open span has the same value, the span continues unchanged (no-op).
    - If an open span has a different value, close it at observed_at and open a new
      one at the same instant. The two spans are adjacent with zero gap.
    """
    key = (source, path)
    existing = open_spans.get(key)
    if existing is None:
        open_spans[key] = OpenSpan(value=value, span_start=observed_at)
        return
    if existing.value == value:
        return
    emitted.append(RawSpan(
        source=source,
        path=list(path),
        value=existing.value,
        start=existing.span_start,
        end=observed_at,
        end_reason="value_change",
    ))
    open_spans[key] = OpenSpan(value=value, span_start=observed_at)


def close_cascade(
    open_spans: OpenSpanMap,
    source: str,
    ancestor: tuple[str, ...],
    closed_at: datetime,
    emitted: list[RawSpan],
) -> None:
    """Close the open span for `ancestor` AND every currently-open descendant for the
    same source.

    Idempotent: if no open span matches, this function is a silent no-op.
    """
    to_close = [
        key for key in open_spans
        if key[0] == source and is_prefix(ancestor, key[1])
    ]
    for key in to_close:
        open_span = open_spans.pop(key)
        emitted.append(RawSpan(
            source=key[0],
            path=list(key[1]),
            value=open_span.value,
            start=open_span.span_start,
            end=closed_at,
            end_reason="closed",
        ))


def finalize_open_spans(open_spans: OpenSpanMap, emitted: list[RawSpan]) -> None:
    """After all snapshots processed, emit remaining open spans with end=None.

    A None end means "still open at the end of known data" — §7.3 clipping will
    assign the `meta-span-open` class and set the rendered end to the query window's
    `to`.
    """
    for (source, path_tuple), open_span in open_spans.items():
        emitted.append(RawSpan(
            source=source,
            path=list(path_tuple),
            value=open_span.value,
            start=open_span.span_start,
            end=None,
            end_reason="open",
        ))


def is_prefix(prefix: tuple[str, ...], full: tuple[str, ...]) -> bool:
    """True if `prefix` is a prefix of `full` (including equal)."""
    return len(prefix) <= len(full) and full[: len(prefix)] == prefix
```

Each function is independently testable:

- `is_prefix` — one-liner, dozens of trivial cases.
- `apply_value` — pre-populate `open_spans`, call, assert state change.
- `close_cascade` — pre-populate with parent + descendants + unrelated siblings,
  call with the parent path, assert only the subtree closed.
- `apply_snapshot` — fixture with both closures and values, assert order-of-operations
  (close-and-reopen lands cleanly).
- `finalize_open_spans` — pre-populate `open_spans`, call, assert every key became a
  `RawSpan` with `end=None`.
- `derive_raw_spans` — end-to-end orchestrator, minimal coverage since the pieces are
  already tested.

**Important invariants:**

- Closures are applied **before** values within the same snapshot. This makes
  "close-and-reopen" (a path present in both `closed` and `values` in one push)
  deterministic: the old span ends at `observed_at`, the new span starts at
  `observed_at` (same moment). Rendered as two adjacent bars with zero gap.
- `close_cascade` matches on `is_prefix`, so closing `("app-A",)` also closes
  `("app-A", "plugin-pkg-1")`, `("app-A", "plugin-pkg-1", "plugin-alpha")`, etc., but
  only for the same source. A different source's `("app-A",)` is unaffected.
- Consecutive identical-value snapshots do **not** create new spans (see `if
  existing_value == value: pass`). The daily heartbeat case (push the same values every
  day for a month) emits one span covering the full month, not 30 spans.
- **Closures are idempotent-safe at derivation time.** `close_cascade` builds its
  `to_close` list from the current `open_spans` map. If no open span matches (because
  the path was already closed, or was never opened by this source), `to_close` is
  empty and the closure is silently a no-op. No error, no stale emission. This means
  a `closed`-only snapshot targeting a path that the source had already closed is
  fully accepted at ingestion (it just stores a closure row) and fully ignored at
  read time (it has nothing to close). Agents can push "close everything I no longer
  see" defensively without needing to track what they've previously closed.
- A `closed`-only snapshot (no `values`) is handled identically to one that has
  `values` — the values loop just iterates zero times. The walk over closures still
  runs and still emits `end_reason="closed"` spans for any actual terminations.

### 7.2 Source conflict resolution (one row per path)

After derivation, multiple `(source, path)` combinations may emit spans for the same
`path`. For Phase 1, we render **one row per path regardless of source** with a simple
deterministic rule: **the source whose most recent observation for that path is latest
wins the entire row; spans from losing sources are dropped entirely**.

```python
# conflict_resolution.py

from collections import defaultdict
from datetime import datetime, timezone

_SENTINEL_OPEN_END = datetime.max.replace(tzinfo=timezone.utc)


def resolve_multi_source_conflicts(
    spans: list[RawSpan],
    asset_id: UUID,
    logger: Logger,
) -> list[RawSpan]:
    """Collapse multi-source conflicts down to one winning source per path.

    For paths where only one source contributed, returns its spans unchanged.
    For paths where multiple sources contributed, picks the source whose most
    recent observation is latest (tie-break: source name alphabetically), drops
    the other sources' spans, and logs a warning.
    """
    spans_by_path = group_spans_by_path(spans)
    resolved: list[RawSpan] = []
    for path_key, path_spans in spans_by_path.items():
        sources_latest = compute_latest_observation_per_source(path_spans)
        if len(sources_latest) == 1:
            resolved.extend(path_spans)
            continue
        winner = pick_winning_source(sources_latest)
        log_source_conflict(logger, asset_id, path_key, sources_latest, winner)
        resolved.extend(span for span in path_spans if span.source == winner)
    return resolved


def group_spans_by_path(
    spans: list[RawSpan],
) -> dict[tuple[str, ...], list[RawSpan]]:
    """Bucket spans by their `path`."""
    result: dict[tuple[str, ...], list[RawSpan]] = defaultdict(list)
    for span in spans:
        result[tuple(span.path)].append(span)
    return result


def compute_latest_observation_per_source(
    path_spans: list[RawSpan],
) -> dict[str, datetime]:
    """For each source touching this path, the timestamp of its latest observation.

    A still-open span (end=None) is treated as "observed at the sentinel future" so
    that any source with a currently-open span beats a source whose spans all have
    known ends in the past. This is the right rule: the most-current data wins.
    """
    latest: dict[str, datetime] = {}
    for span in path_spans:
        observed_at = span.end if span.end is not None else _SENTINEL_OPEN_END
        if span.source not in latest or latest[span.source] < observed_at:
            latest[span.source] = observed_at
    return latest


def pick_winning_source(sources_latest: dict[str, datetime]) -> str:
    """Primary key: most recent observation. Secondary key: source name alphabetical.

    The secondary key makes the outcome deterministic when two sources have the
    same most-recent timestamp (rare but possible with heartbeat pushes).
    """
    return max(sources_latest.items(), key=lambda kv: (kv[1], kv[0]))[0]


def log_source_conflict(
    logger: Logger,
    asset_id: UUID,
    path: tuple[str, ...],
    sources_latest: dict[str, datetime],
    winner: str,
) -> None:
    """Emit an operator-visible warning about a multi-source conflict.

    Isolated as its own function so tests can assert the warning is emitted without
    mocking the entire resolve function.
    """
    logger.warning(
        "asset_meta_timeline.multi_source_conflict",
        extra={
            "asset_id": str(asset_id),
            "path": list(path),
            "sources": sorted(sources_latest.keys()),
            "winner": winner,
        },
    )
```

**Why drop losing sources entirely** (rather than interleave them per time point): the
interleaved rule is hard to reason about, hard to test exhaustively, and hard to
explain in a tooltip. Drop-entirely is deterministic, easy to unit-test, and produces
the visually clean "one source's story per row" outcome. The cost is that if two
sources legitimately own different *slices of time* for the same path (e.g. source A
tracked Mar 1–15 and source B tracked Mar 16–31), the loser's slice is invisible. This
is acceptable for Phase 1 because **that scenario is a source-ownership bug** — two
sources should not fight over the same path. The warning log surfaces these cases for
operators to correct.

If Phase 2 needs to visualize both, the fix is one row per `(source, path)` rather
than one per `path` — a Phase 2 change to §7.4 tree building, not a model change.

**Testability:** each of the five functions is tested in isolation. `pick_winning_source`
alone has ~10 tiny test cases covering the tie-break logic. `log_source_conflict` is
tested by asserting a caplog fixture captures the right `extra` fields.

### 7.3 Window clipping

After conflict resolution, clip each span to `[window_from, window_to]`:

```python
# clipping.py

def clip_spans(
    spans: list[RawSpan],
    window_from: datetime,
    window_to: datetime,
) -> list[ClippedSpan]:
    """Clip every span to [window_from, window_to] and drop ones outside the window.

    One-to-zero-or-one transform (spans outside the window produce None).
    """
    return [
        clipped
        for span in spans
        if (clipped := clip_one_span(span, window_from, window_to)) is not None
    ]


def clip_one_span(
    span: RawSpan,
    window_from: datetime,
    window_to: datetime,
) -> ClippedSpan | None:
    """Clip a single span to the window. Return None if entirely outside."""
    effective_end = span.end if span.end is not None else window_to
    if effective_end <= window_from:
        return None  # entirely before window
    if span.start >= window_to:
        return None  # entirely after window

    clipped_start = max(span.start, window_from)
    clipped_end = min(effective_end, window_to)
    classes = compute_span_classes(
        span=span,
        window_from=window_from,
        window_to=window_to,
        clipped_start=clipped_start,
    )
    return ClippedSpan(
        source=span.source,
        path=span.path,
        value=span.value,
        start=clipped_start,
        end=clipped_end,
        className=" ".join(classes),
    )


def compute_span_classes(
    span: RawSpan,
    window_from: datetime,
    window_to: datetime,
    clipped_start: datetime,
) -> list[str]:
    """Compute the CSS class list for one span based on how it sits in the window.

    Pure function of the span + window. The classes describe VISUAL meaning only;
    the caller has already decided to include this span in the output.
    """
    classes = ["meta-span"]
    if clipped_start > span.start:
        classes.append("meta-span-clipped-left")
    if span.end is None:
        classes.append("meta-span-open")
    elif span.end > window_to:
        classes.append("meta-span-clipped-right")
    if span.end_reason == "closed":
        classes.append("meta-span-closed")
    return classes
```

**Testability:** `compute_span_classes` is the most important pure function to
exhaust — every (clipped_start ?> span.start) × (span.end is None | > window_to | ≤
window_to) × (end_reason == "closed" | not) combination is a test case. `clip_one_span`
adds a handful of boundary cases (span exactly at window edge, zero-length span,
etc.). `clip_spans` is a trivial composition.

**Class semantics (consumed by `meta-timeline.css`):**

| Class | Meaning |
|---|---|
| `meta-span` | Base class applied to every span. Sets default bar styling. |
| `meta-span-clipped-left` | This span started before the visible window. Rendered with a faded/dashed left edge to communicate "origin unknown within view". |
| `meta-span-clipped-right` | This span continues past the visible window with a known value change after `to`. Faded/dashed right edge meaning "known continuation outside view". |
| `meta-span-open` | This span is still open at the right edge of known data (no closure, no newer value). Rendered with an arrow-style / soft-fade right edge meaning "still ongoing as far as we know". |
| `meta-span-closed` | This span was explicitly terminated by a closure event. Rendered with a solid cap on the right edge. Purely additive to the base class. |

### 7.4 Tree building (groups with nestedGroups)

After clipping, build the vis-timeline `groups` list:

```python
# tree_builder.py

from collections import defaultdict
import json


def build_groups_wire(clipped_spans: list[ClippedSpan]) -> list[dict]:
    """Build the vis-timeline `groups` list from clipped spans.

    Walks distinct paths, synthesizes intermediate container groups so every
    ancestor exists even if only a leaf has data, attaches nestedGroups to parents,
    and sorts deterministically for test stability.
    """
    distinct_paths = collect_distinct_paths(clipped_spans)
    all_group_paths = expand_with_synthetic_ancestors(distinct_paths)
    children_map = compute_children_map(all_group_paths)
    return [
        build_group_entry(path, children_map)
        for path in sort_groups_deterministically(all_group_paths)
    ]


def collect_distinct_paths(
    spans: list[ClippedSpan],
) -> set[tuple[str, ...]]:
    """Extract the set of distinct path tuples present in the clipped spans."""
    return {tuple(span.path) for span in spans}


def expand_with_synthetic_ancestors(
    paths: set[tuple[str, ...]],
) -> set[tuple[str, ...]]:
    """Return `paths` plus every ancestor prefix.

    Ensures intermediate container groups exist for render. E.g. if the only
    leaf is ("app-A", "pkg-1", "alpha"), the result contains ("app-A",),
    ("app-A", "pkg-1"), and ("app-A", "pkg-1", "alpha").
    """
    expanded: set[tuple[str, ...]] = set()
    for path in paths:
        for length in range(1, len(path) + 1):
            expanded.add(path[:length])
    return expanded


def compute_children_map(
    paths: set[tuple[str, ...]],
) -> dict[tuple[str, ...], list[tuple[str, ...]]]:
    """Build a parent → immediate-children map from the full group-path set.

    Only immediate children are recorded; vis-timeline handles transitive
    nesting via the `nestedGroups` chain.
    """
    result: dict[tuple[str, ...], list[tuple[str, ...]]] = defaultdict(list)
    for path in paths:
        if len(path) > 1:
            result[path[:-1]].append(path)
    return result


def sort_groups_deterministically(
    paths: set[tuple[str, ...]],
) -> list[tuple[str, ...]]:
    """Stable ordering for test determinism.

    Primary key: depth ASC (roots first). Secondary: path lexicographically.
    The ordering affects the DataSet emission order; vis-timeline still resolves
    parent/child visually via nestedGroups regardless of emission order, so this
    sort is about test stability, not render correctness.
    """
    return sorted(paths, key=lambda p: (len(p), p))


def build_group_entry(
    path: tuple[str, ...],
    children_map: dict[tuple[str, ...], list[tuple[str, ...]]],
) -> dict:
    """Build one group dict. Adds nestedGroups/showNested iff the path has children."""
    entry: dict = {
        "id": encode_path_as_group_id(path),
        "content": path[-1],
    }
    if path in children_map:
        children_sorted = sorted(children_map[path])
        entry["nestedGroups"] = [encode_path_as_group_id(c) for c in children_sorted]
        entry["showNested"] = False
    return entry


def encode_path_as_group_id(path: tuple[str, ...]) -> str:
    """Single point of truth for path → vis-timeline group id encoding.

    Used by both tree_builder and item_emitter so the two agree on identity.
    """
    return json.dumps(list(path), ensure_ascii=False, separators=(",", ":"))
```

**Key point: synthetic intermediates.** If the only path with data is
`["app-A", "plugin-pkg-1", "plugin-alpha"]`, `expand_with_synthetic_ancestors`
produces groups for `["app-A"]` and `["app-A", "plugin-pkg-1"]`. Both are pure
containers (no items will target them) but they exist as group rows with chevrons so
the user can collapse the subtree. Without synthetics, vis-timeline would have no
group for the child to attach to via `nestedGroups` and would render the leaf as
top-level.

**Testability:** each helper is unit-tested in isolation:

- `collect_distinct_paths` — given spans with duplicates and variants, returns the
  expected set.
- `expand_with_synthetic_ancestors` — leaf-only input produces intermediate ancestors.
- `compute_children_map` — parent with two children returns both; leaf is absent as
  a key.
- `sort_groups_deterministically` — deterministic output regardless of input order.
- `build_group_entry` — with and without children.
- `encode_path_as_group_id` — path with special characters (`:`, `/`, quotes,
  Unicode) encodes without ambiguity.
- `build_groups_wire` — end-to-end composition over a realistic fixture.

### 7.5 Item emission

```python
# item_emitter.py

from .tree_builder import encode_path_as_group_id


def build_items_wire(spans: list[ClippedSpan]) -> list[dict]:
    """Convert clipped spans to vis-timeline items.

    One-to-one transform; no aggregation, no filtering (clipping already removed
    out-of-window spans).
    """
    return [item_from_span(span, index) for index, span in enumerate(spans)]


def item_from_span(span: ClippedSpan, index: int) -> dict:
    """Build one vis-timeline item dict from a clipped span."""
    return {
        "id": f"s{index}",
        "group": encode_path_as_group_id(tuple(span.path)),
        "content": span.value,
        "start": span.start.isoformat(),
        "end":   span.end.isoformat(),
        "type":  "range",
        "className": span.className,
        "source": span.source,
    }
```

Note: `encode_path_as_group_id` is imported from `tree_builder` so both modules
share one definition (DRY). vis-timeline passes extra fields through unchanged on
`Item` objects and makes them available inside `tooltip.template(item)`. The
`source` field is carried purely so the tooltip can display it; vis-timeline itself
does nothing with it.

**Testability:** `item_from_span` is a trivial pure transform — one test per field to
confirm it lands. `build_items_wire` is a one-liner composition, one end-to-end test.

### 7.6 Top-level orchestration

The five stages above are composed by a single public function:

```python
# orchestrator.py

from .derivation import derive_raw_spans
from .conflict_resolution import resolve_multi_source_conflicts
from .clipping import clip_spans
from .tree_builder import build_groups_wire
from .item_emitter import build_items_wire


def build_timeline_response(
    asset_id: UUID,
    snapshots: list[SnapshotWithEntries],
    window_from: datetime,
    window_to: datetime,
    logger: Logger,
) -> dict:
    """Pure composition of the five stages. Zero I/O.

    The caller (the read-side service) owns snapshot loading and response
    serialization. This function is the only public entry point of the
    derivation stack.
    """
    raw_spans = derive_raw_spans(snapshots)
    resolved = resolve_multi_source_conflicts(raw_spans, asset_id, logger)
    clipped = clip_spans(resolved, window_from, window_to)
    return {
        "groups": build_groups_wire(clipped),
        "items":  build_items_wire(clipped),
    }
```

This is **the** function the read service calls. It is a 5-line composition with no
branching of its own; correctness comes from the tested correctness of its parts.
Integration tests cover the composition end-to-end with real snapshots (§10.2).

### 7.7 Performance and caching

Phase 1 does no caching. The derivation algorithm is O(total snapshots for asset) and
runs in-process during the request. At expected volumes (< 10k snapshots per asset per
year, each with < 100 entries), a request completes in well under 100 ms.

If measurement later shows this endpoint as hot, the natural optimization is a Redis
cache keyed on `(asset_id, from, to)` with a short TTL (60 s) and a bust on snapshot
write. **Out of scope for Phase 1** — add only with evidence.

---

## 8. Ingestion write path

### 8.1 Service layer

```
api/tropek/modules/asset_meta/
├── __init__.py
├── schemas.py                  # Pydantic request/response
├── params.py                   # internal parameter objects
├── repositories.py             # DB access (async SQLAlchemy)
├── service.py                  # thin orchestrator — validate, exist, write, read
├── router.py                   # FastAPI routes
└── timeline/                   # pure derivation stack; zero I/O below this line
    ├── __init__.py             # re-exports the public top-level functions
    ├── types.py                # RawSpan, ClippedSpan, SnapshotWithEntries, OpenSpan
    ├── derivation.py           # §7.1
    ├── conflict_resolution.py  # §7.2
    ├── clipping.py             # §7.3
    ├── tree_builder.py         # §7.4
    ├── item_emitter.py         # §7.5
    ├── summary.py              # §6.7 count_distinct_leaf_paths
    └── orchestrator.py         # §7.6 build_timeline_response
```

**Why a sub-package for the pure derivation stack:** the ~20 small functions split
across 7 files (plus `types.py`) is arguably more structure than a single
`timeline.py` would have — but it keeps each file small and focused. Each function is
~10–30 lines, each file is ~30–100 lines. No single file becomes a monolith. The
sub-package boundary (`asset_meta.timeline`) is a clear "pure code only, no I/O"
zone — anything that needs a DB session or HTTP context belongs in `service.py` or
`router.py`.

If the implementer finds this over-structured during implementation, they may
collapse to fewer files (e.g., merge `item_emitter.py` into `tree_builder.py`) as
long as every function listed in §7 keeps its own name, signature, and focused unit
tests. The *function* decomposition is the binding contract; the *file* layout is a
strong suggestion.

**Why a new module.** Asset meta is conceptually adjacent to the existing `assets`
module but has independent CRUD semantics, its own schemas, and its own read algorithm.
Keeping it in its own module follows the pattern already used by `sli_registry`,
`slo_registry`, and `quality_gate` — one subsystem per module, clean module boundary.

### 8.2 Pydantic request models

```python
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from tropek.modules.common.schemas import StrictInput

class MetaValueInput(StrictInput):
    path: list[str] = Field(min_length=1, max_length=6)
    value: str = Field(max_length=1024)

    @field_validator("path")
    @classmethod
    def _validate_path_entries(cls, value: list[str]) -> list[str]:
        for entry in value:
            if not 1 <= len(entry) <= 128:
                raise ValueError("path entries must be 1-128 characters")
        return value


class MetaClosureInput(StrictInput):
    path: list[str] = Field(min_length=1, max_length=6)

    @field_validator("path")
    @classmethod
    def _validate_path_entries(cls, value: list[str]) -> list[str]:
        for entry in value:
            if not 1 <= len(entry) <= 128:
                raise ValueError("path entries must be 1-128 characters")
        return value


class MetaSnapshotCreate(StrictInput):
    source: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9._-]+$")
    observed_at: datetime
    values: list[MetaValueInput] = Field(default_factory=list, max_length=10_000)
    closed: list[MetaClosureInput] = Field(default_factory=list, max_length=1_000)

    @field_validator("values")
    @classmethod
    def _unique_value_paths(cls, entries: list[MetaValueInput]) -> list[MetaValueInput]:
        seen: set[tuple[str, ...]] = set()
        for entry in entries:
            key = tuple(entry.path)
            if key in seen:
                raise ValueError(f"duplicate path in values: {entry.path}")
            seen.add(key)
        return entries

    @field_validator("closed")
    @classmethod
    def _unique_closed_paths(cls, entries: list[MetaClosureInput]) -> list[MetaClosureInput]:
        seen: set[tuple[str, ...]] = set()
        for entry in entries:
            key = tuple(entry.path)
            if key in seen:
                raise ValueError(f"duplicate path in closed: {entry.path}")
            seen.add(key)
        return entries


class MetaSnapshotCreated(BaseModel):
    snapshot_id: UUID
```

A service-layer check enforces "`values` OR `closed` non-empty"; it is not expressible
as a per-field validator.

### 8.3 Service methods

The ingest and read services each decompose into small helpers. `_ensure_asset_exists`
is shared by both (DRY).

```python
# service.py

async def create_meta_snapshot(
    session: AsyncSession,
    asset_id: UUID,
    payload: MetaSnapshotCreate,
) -> MetaSnapshotCreated:
    """Ingest one snapshot. Thin orchestrator over validation + existence + write."""
    _validate_payload_has_content(payload)
    await _ensure_asset_exists(session, asset_id)
    snapshot_id = await _write_snapshot_rows(session, asset_id, payload)
    await session.commit()
    return MetaSnapshotCreated(snapshot_id=snapshot_id)


async def get_timeline(
    session: AsyncSession,
    asset_id: UUID,
    window_from: datetime,
    window_to: datetime,
) -> TimelineResponse:
    """Read one asset's timeline. Thin orchestrator over load + derive."""
    await _ensure_asset_exists(session, asset_id)
    snapshots = await meta_repo.load_snapshots_for_derivation(
        session, asset_id=asset_id, until=window_to,
    )
    wire = build_timeline_response(
        asset_id=asset_id,
        snapshots=snapshots,
        window_from=window_from,
        window_to=window_to,
        logger=logger,
    )
    return TimelineResponse.model_validate(wire)


# --- private helpers ---------------------------------------------------------

def _validate_payload_has_content(payload: MetaSnapshotCreate) -> None:
    """Reject snapshots with neither values nor closures.

    Pure function. Pydantic cannot express this cross-field rule at the field
    validator level, so it lives in the service layer.
    """
    if not payload.values and not payload.closed:
        raise AssetMetaValidationError("snapshot must contain values or closed")


async def _ensure_asset_exists(session: AsyncSession, asset_id: UUID) -> None:
    """Raise AssetNotFoundError if the asset does not exist.

    Shared by both create_meta_snapshot and get_timeline. Putting the check in
    one place means both endpoints return a consistent 404 shape.
    """
    if not await asset_repo.asset_exists(session, asset_id):
        raise AssetNotFoundError(asset_id)


async def _write_snapshot_rows(
    session: AsyncSession,
    asset_id: UUID,
    payload: MetaSnapshotCreate,
) -> UUID:
    """Insert the snapshot + values + closures rows. Does not commit."""
    snapshot = await meta_repo.insert_snapshot(
        session,
        asset_id=asset_id,
        source=payload.source,
        observed_at=payload.observed_at,
    )
    if payload.values:
        await meta_repo.insert_values(session, snapshot.id, payload.values)
    if payload.closed:
        await meta_repo.insert_closures(session, snapshot.id, payload.closed)
    return snapshot.id
```

**Why decompose the service even when the code is already short:** each helper can be
tested in isolation with a lightweight async fixture, and the public orchestrators
read as a plain English description of what they do (validate, check existence,
write). Adding a future concern (e.g. rate limiting, audit log writes, metrics
emission) slots in as another line in the orchestrator without bloating any single
helper.

---

## 9. UI component

### 9.1 File layout

```
ui/src/features/meta_timeline/
├── api.ts                  # fetch fn; returns TimelineResponse (already vis-timeline shape)
├── domain.ts               # domain types — thin wrappers over wire types, date parsing
├── mappers.ts              # dtoToTimelineResponse (just parses ISO strings → Date)
├── hooks.ts                # useMetaTimeline(assetId, from, to)
├── index.ts                # re-exports domain types + hooks
└── components/
    ├── MetaTimelineSection.tsx    # collapsible card, owns section state
    ├── MetaTimeline.tsx           # thin React wrapper around vis.Timeline
    ├── renderSpanTooltip.tsx      # tooltip template function (shared by wrapper)
    └── meta-timeline.css          # class styles for span classes + marker
```

**The feature lives in a new top-level `features/meta_timeline/` directory**, not nested
under `features/evaluations/`. Rationale: meta is an asset-level concept that happens to
be rendered inside the eval detail page in Phase 1. Phase 3 will add an asset-level
dashboard page that also consumes this feature. Putting it under `evaluations/` would
force a rename later. Start it in the right place.

It follows the DTO/Domain/Mapper pattern from `docs/superpowers/specs/2026-04-12-ui-layering-design.md`:

- **DTOs** are the types generated from the OpenAPI schema for the read endpoint.
- **Domain types** in `domain.ts` are almost identical to the DTOs except that `start`
  and `end` are real `Date` objects. Everything else (the vis-timeline-shaped `groups`,
  `items`, class strings, group ids) is preserved verbatim — the wire IS the UI shape.
- **Mapper** (`dtoToTimelineResponse`) is effectively a one-function identity-with-dates.
  Sync, no fetch, no await.

### 9.2 The collapsible section

The section is rendered as a **compact single-row strip** by default — so it does not
disrupt the primary eval-detail flow of heatmap → scores → SLI breakdown table. A
user investigating "what changed" clicks the strip to expand it into the full
vis-timeline component.

**Collapsed state** (default) — a one-row strip showing:

- A chevron/caret indicating expandability.
- The label `Asset meta · <N> items tracked` (where N is a lightweight count, see
  below).
- A right-aligned subtle hint like `click to investigate changes over time`.
- Total visual height: ~32px — comparable to a single table row.

**Expanded state** — the strip becomes a card header with a close control, and the
vis-timeline renders beneath it at 340px fixed height.

```tsx
// MetaTimelineSection.tsx
interface Props {
  assetId: string
  focusEval: { periodEnd: Date; id: string }
}

export function MetaTimelineSection({ assetId, focusEval }: Props) {
  const [isExpanded, setIsExpanded] = useState(false)  // default collapsed

  const from = useMemo(() => subDays(focusEval.periodEnd, 30), [focusEval.periodEnd])
  const to   = useMemo(() => addDays(focusEval.periodEnd, 7),  [focusEval.periodEnd])

  // Always fetch a lightweight "count" of how many items are tracked, so the
  // collapsed strip can show it. This is a tiny query — O(distinct paths),
  // ~100 bytes — and does not wait for expand. Uses a separate hook so the
  // full-data query is still gated on isExpanded.
  const { data: summary } = useMetaTimelineSummary(assetId, from, to)

  const { data, isLoading, error } = useMetaTimeline(assetId, from, to, {
    enabled: isExpanded,
  })

  return (
    <div className="meta-timeline-section">
      <CollapsedStrip
        itemCount={summary?.itemCount ?? 0}
        expanded={isExpanded}
        onToggle={() => setIsExpanded((v) => !v)}
      />
      {isExpanded && (
        <div className="meta-timeline-body">
          {isLoading && <LoadingIndicator />}
          {error && <ErrorState error={error} />}
          {data && data.items.length === 0 && <EmptyState />}
          {data && data.items.length > 0 && (
            <MetaTimeline
              groups={data.groups}
              items={data.items}
              focusTime={focusEval.periodEnd}
              focusLabel="This evaluation"
              windowStart={from}
              windowEnd={to}
            />
          )}
        </div>
      )}
    </div>
  )
}


function CollapsedStrip({
  itemCount, expanded, onToggle,
}: {
  itemCount: number
  expanded: boolean
  onToggle: () => void
}) {
  const itemsText =
    itemCount === 0 ? "no items tracked"
    : itemCount === 1 ? "1 item tracked"
    : `${itemCount} items tracked`

  return (
    <button
      type="button"
      onClick={onToggle}
      className="meta-timeline-strip"
      aria-expanded={expanded}
    >
      <ChevronIcon direction={expanded ? "down" : "right"} />
      <span className="meta-timeline-strip-label">Asset meta</span>
      <span className="meta-timeline-strip-separator">·</span>
      <span className="meta-timeline-strip-count">{itemsText}</span>
      {!expanded && (
        <span className="meta-timeline-strip-hint">
          click to investigate changes over time
        </span>
      )}
    </button>
  )
}
```

**Design rationale — why a single-row collapsed strip, not a "card with header":**

- The natural flow of the eval-detail page is heatmap → numbers → table. The meta
  timeline is an **investigation tool**, not a primary artifact. It should be
  present but unobtrusive by default, so it adds roughly one row of vertical space
  to the page when not in use.
- The item count in the collapsed strip is a small affordance: users can see at a
  glance whether there's anything *worth* investigating. An asset with zero tracked
  items gives the user the "no news" signal without requiring them to expand.
- A dedicated `useMetaTimelineSummary` hook fetches **only the count** (a tiny
  endpoint returning `{itemCount: number}`), so the collapsed state is cheap and
  always reflects reality. See §6.7 below for the summary endpoint contract.
- The strip expands in place — it does not navigate, does not open a modal, does
  not push other content off-screen. Expanding adds ~340px of vertical height in
  place; collapsing restores the flow.

**Key properties:**

- **Default collapsed.** Users opt in by clicking. The heatmap, scores, and SLI
  breakdown remain the primary flow for normal use. Users only expand during
  investigation — "something changed here, let me see what".
- **Full-data query is gated on `isExpanded`.** The heavy `GET /meta/timeline`
  request is only issued when the user expands the section. Subsequent
  collapse/expand cycles reuse the cached query result (standard React Query
  behavior).
- **Summary query runs unconditionally** when the section is mounted — but it is
  tiny and cached aggressively.
- **`from` / `to` are computed locally.** Asymmetric window: 30 days of history
  before the focus eval, 7 days of trailing context to show open-ended spans
  leaving the current state.

**Note: new summary endpoint.** The collapsed-strip item count requires a second,
lightweight server endpoint. This is added to §6 as **§6.7** — one new short section
documenting it.

### 9.3 The vis-timeline React wrapper

```tsx
// MetaTimeline.tsx
interface Props {
  groups: Group[]
  items: Item[]
  focusTime: Date
  focusLabel: string
  windowStart: Date
  windowEnd: Date
}

export function MetaTimeline({
  groups, items, focusTime, focusLabel, windowStart, windowEnd,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const timelineRef = useRef<Timeline | null>(null)
  const groupsDataSetRef = useRef<DataSet<Group> | null>(null)
  const itemsDataSetRef = useRef<DataSet<Item> | null>(null)

  // Create the Timeline once on mount.
  useEffect(() => {
    if (!containerRef.current) return

    const groupsDataSet = new DataSet<Group>(groups)
    const itemsDataSet = new DataSet<Item>(items)
    groupsDataSetRef.current = groupsDataSet
    itemsDataSetRef.current = itemsDataSet

    const timeline = new Timeline(
      containerRef.current,
      itemsDataSet,
      groupsDataSet,
      {
        orientation: "top",
        height: 340,
        start: windowStart,
        end: windowEnd,
        // min/max cap the user's pan to the fetched window. Panning further would
        // show empty space because no data was fetched outside it. If Phase 2 adds
        // dynamic re-fetching on `rangechanged`, these caps can be widened.
        min: windowStart,
        max: windowEnd,
        zoomMin: 1000 * 60 * 60,                     // 1 hour
        zoomMax: (windowEnd.getTime() - windowStart.getTime()),  // can't zoom out beyond the fetched window

        editable: false,
        selectable: false,
        moveable: true,     // pan is allowed
        zoomable: true,     // wheel zoom is allowed

        showCurrentTime: false,  // we don't care about "now"
        showTooltips: true,
        stack: false,            // one row per group, always
        groupHeightMode: "fixed",
        margin: { axis: 12, item: { horizontal: 0, vertical: 4 } },

        tooltip: {
          followMouse: false,
          overflowMethod: "flip",
          delay: 250,
          template: renderSpanTooltip,
        },
      },
    )

    timeline.addCustomTime(focusTime, "focus-eval")
    timeline.setCustomTimeMarker(focusLabel, "focus-eval", false)

    timelineRef.current = timeline

    return () => {
      timeline.destroy()
      timelineRef.current = null
      groupsDataSetRef.current = null
      itemsDataSetRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])  // create-once; data updates handled in the next effect

  // Update data sets on prop changes without tearing down the Timeline.
  useEffect(() => {
    if (groupsDataSetRef.current) {
      groupsDataSetRef.current.clear()
      groupsDataSetRef.current.add(groups)
    }
    if (itemsDataSetRef.current) {
      itemsDataSetRef.current.clear()
      itemsDataSetRef.current.add(items)
    }
  }, [groups, items])

  // Move the focus marker if the viewed eval changes.
  useEffect(() => {
    if (timelineRef.current) {
      timelineRef.current.setCustomTime(focusTime, "focus-eval")
    }
  }, [focusTime])

  return <div ref={containerRef} className="meta-timeline-container" />
}
```

**Key points:**

- **Create-once pattern.** The Timeline instance is created in a `useEffect` with `[]`
  deps and destroyed in the cleanup. Re-creating it on every prop change would thrash
  the DOM and leak event listeners.
- **DataSet mutation for data updates.** `clear() + add()` is simple and correct at
  Phase 1 data volumes. Incremental diffing (only update changed items) is a
  premature optimization.
- **React does not manage the inner DOM.** The container `<div>` is given to
  vis-timeline via `useRef`, and vis-timeline mutates its children directly. React
  never re-renders into this element. This avoids hydration / reconciliation issues.
- **Cleanup calls `timeline.destroy()`.** Required for hot-reload safety and to avoid
  memory leaks when the section is collapsed (since React will unmount `MetaTimeline`
  when `isExpanded` flips to false).

### 9.4 CSS classes — full vocabulary

```css
/* meta-timeline.css */

.meta-timeline-container {
  /* component-level defaults */
}

.vis-item.meta-span {
  background-color: var(--color-meta-span-bg);
  border-color: var(--color-meta-span-border);
  border-radius: 3px;
  color: var(--color-meta-span-fg);
  font-family: "system-ui", -apple-system, sans-serif;
  font-size: 12px;
}

.vis-item.meta-span-clipped-left {
  border-left-style: dashed;
  mask-image: linear-gradient(to right, transparent 0, black 12px);
}

.vis-item.meta-span-clipped-right {
  border-right-style: dashed;
  mask-image: linear-gradient(to left, transparent 0, black 12px);
}

.vis-item.meta-span-open {
  border-right-style: none;
  mask-image: linear-gradient(to left, transparent 0, black 20px);
}

.vis-item.meta-span-closed {
  border-right-width: 3px;
  border-right-style: solid;
}

/* Focus-eval marker override. */
.vis-custom-time.focus-eval {
  background-color: var(--color-focus-eval-marker);
  width: 2px;
}

.vis-custom-time.focus-eval > .vis-custom-time-marker {
  background-color: var(--color-focus-eval-marker);
  color: var(--color-focus-eval-marker-fg);
  padding: 2px 6px;
  border-radius: 3px;
  font-family: "system-ui", -apple-system, sans-serif;
  font-size: 11px;
}
```

**Theme variables** are added to `ui/src/index.css` for each theme (dark / current /
light) following the existing convention. The marker's color is deliberately distinct
from the span colors to make it read as "viewport metadata", not "another span".

### 9.5 Tooltip template

The server does not populate a `title` field (see note in §6.4.2). Instead, the UI
configures vis-timeline's `tooltip.template` option with a function that receives the
full `Item` object (including our extra `source` field) and returns an HTML string:

```tsx
// renderSpanTooltip.tsx
import { format, formatDistanceStrict } from "date-fns"

export function renderSpanTooltip(item: Item): string {
  const start = format(parseIsoDate(item.start), "MMM d yyyy, HH:mm 'UTC'")
  const end   = format(parseIsoDate(item.end),   "MMM d yyyy, HH:mm 'UTC'")
  const duration = formatDistanceStrict(parseIsoDate(item.start), parseIsoDate(item.end))

  const classes = item.className ?? ""
  const isOpen       = classes.includes("meta-span-open")
  const clippedLeft  = classes.includes("meta-span-clipped-left")
  const clippedRight = classes.includes("meta-span-clipped-right")
  const isClosed     = classes.includes("meta-span-closed")

  const fromAnnotation = clippedLeft ? " (started before window)" : ""
  const toAnnotation =
    clippedRight ? " (continues after window)"
    : isOpen    ? " (still open)"
    : isClosed  ? " (explicit closure)"
    : ""

  return [
    `<strong>${escapeHtml(decodeGroupLabel(item.group))}</strong>`,
    `Value: <code>${escapeHtml(item.content)}</code>`,
    `From: ${start}${fromAnnotation}`,
    `To: ${end}${toAnnotation}`,
    `Duration: ${duration}`,
    `Source: <code>${escapeHtml(item.source)}</code>`,
  ].join("<br />")
}
```

Helper functions:

- `decodeGroupLabel(groupId)` parses the JSON-encoded group id into a path and joins
  with " > " for display (e.g. `'["app-A","plugin-pkg-1","plugin-alpha"]'` →
  `"app-A > plugin-pkg-1 > plugin-alpha"`).
- `escapeHtml(s)` escapes `&`, `<`, `>`, `"`, `'` to avoid injection from user-supplied
  values.
- `parseIsoDate(s)` wraps `new Date(s)` for testability.

The example uses `date-fns` because it is already in TROPEK's UI dependencies. If a
different formatter lib is preferred, swap it — the shape is what matters.

### 9.6 Integration into the evaluation detail page

**Placement: between the heatmap and the first table in the eval detail view.** The
collapsed strip sits as a thin row immediately below the heatmap/score block and
immediately above the SLI breakdown table (or whichever table is the first in the
detail page). When collapsed it adds ~32px of vertical space — roughly a single
table row — and does not disrupt the flow from heatmap → scores → detailed
breakdown.

```
┌─────────────────────────────────────────────────────────┐
│  Evaluation header (asset, time, score, status)         │
├─────────────────────────────────────────────────────────┤
│  Heatmap / score block                                  │
├─────────────────────────────────────────────────────────┤
│  ▸ Asset meta · 7 items tracked · click to investigate… │  ← collapsed strip (default)
├─────────────────────────────────────────────────────────┤
│  SLI breakdown table (first table in the page)          │
├─────────────────────────────────────────────────────────┤
│  Evaluation actions / notes / ...                       │
└─────────────────────────────────────────────────────────┘
```

When expanded, the strip becomes a header and the full vis-timeline renders
beneath it at 340px height, pushing the SLI table down the page in place:

```
┌─────────────────────────────────────────────────────────┐
│  Heatmap / score block                                  │
├─────────────────────────────────────────────────────────┤
│  ▾ Asset meta · 7 items tracked                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │  [vis-timeline — 340px — focus eval marker]       │  │
│  └───────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│  SLI breakdown table                                    │
└─────────────────────────────────────────────────────────┘
```

**Locating the insertion point:** find the component that renders the evaluation
detail body (search for where `EvaluationHeatmap` is rendered — the insertion point
is directly after that block and directly before `SLIBreakdownTable` or similar).
The section is a sibling of the surrounding blocks, not nested inside any existing
card.

**The section is always rendered** when an eval is loaded (regardless of whether
the asset has any meta data). For assets with no meta data, the collapsed strip
shows "no items tracked" so users discover the feature exists and know how to start
pushing. Expanding an empty-data section shows the empty-state copy from §6.5.

**Why default-collapsed is the right default:** the natural flow of the eval detail
page is heatmap → data → graphs → tables. Users reviewing a routine eval do not
need to see the meta timeline — they want to confirm the result and move on. The
timeline exists for a specific use case: "this eval failed/regressed, let me see
what changed on the asset recently". Default-collapsed keeps the primary flow clean
for routine use and surfaces the timeline on demand for investigation.

---

## 10. Testing strategy

### 10.1 Pure unit tests (derivation, conflict, clipping, tree building)

The server-side algorithm is decomposed into ~20 small pure functions (§7). Each one
gets **its own focused test section** with a small fixture — not just end-to-end
tests on the top-level orchestrator. Test files live in
`api/tests/engine/asset_meta/`, one file per module:

```
api/tests/engine/asset_meta/
├── test_derivation.py           # tests for §7.1 functions
├── test_conflict_resolution.py  # tests for §7.2 functions
├── test_clipping.py             # tests for §7.3 functions
├── test_tree_builder.py         # tests for §7.4 functions
├── test_item_emitter.py         # tests for §7.5 functions
└── test_orchestrator.py         # end-to-end composition sanity (§7.6)
```

**Per-function test coverage (minimum):**

| Function | Minimum test cases |
|---|---|
| `is_prefix` | true/false for equal, prefix-of, suffix-of, disjoint, empty |
| `apply_value` | new key opens span; same value no-op; different value closes + opens |
| `close_cascade` | closes exact match; closes descendants; ignores other sources; ignores non-existent path (idempotent) |
| `apply_snapshot` | closures-before-values ordering; close-and-reopen in one push |
| `finalize_open_spans` | converts remaining map entries to open-ended RawSpans |
| `derive_raw_spans` | 3–4 integration fixtures exercising the algorithm end-to-end |
| `group_spans_by_path` | empty, single path, multiple paths |
| `compute_latest_observation_per_source` | open-span sentinel beats closed past; multiple sources |
| `pick_winning_source` | clear winner; tie-break on source name |
| `log_source_conflict` | asserts `extra` fields via `caplog` |
| `resolve_multi_source_conflicts` | single source (no-op); conflict (winner selected, loser dropped, warning logged) |
| `compute_span_classes` | every combination of (clipped-left/not) × (end None/past/within) × (closed/not) — ~12 cases |
| `clip_one_span` | entirely before; entirely after; inside; boundary cases (span starts at `window_from`, ends at `window_to`); zero-length |
| `clip_spans` | composition over a small list |
| `collect_distinct_paths` | deduplication |
| `expand_with_synthetic_ancestors` | leaf-only input; already-expanded input is a no-op |
| `compute_children_map` | parent with multiple children; leaf has no entry |
| `sort_groups_deterministically` | order-independent input → deterministic output |
| `build_group_entry` | with and without children |
| `encode_path_as_group_id` | path with special chars (`:`, `/`, `"`, Unicode) round-trips via `json.loads` |
| `build_groups_wire` | end-to-end composition fixture |
| `item_from_span` | one test per output field |
| `build_items_wire` | trivial composition, one small fixture |
| `build_timeline_response` | 3 realistic fixtures (simple asset, hierarchical asset, multi-source asset with conflict) |

**Service-layer tests** (in `api/tests/engine/asset_meta/test_service.py`, still no
real DB — use in-memory fakes for the repositories):

| Function | Minimum test cases |
|---|---|
| `_validate_payload_has_content` | empty snapshot raises; values-only passes; closed-only passes; both passes |
| `_ensure_asset_exists` | exists → no exception; missing → `AssetNotFoundError` |
| `_write_snapshot_rows` | values-only; closed-only; both; empty lists skipped |

**End-to-end scenario coverage** (exercised by `test_orchestrator.py` and
`test_derivation.py::test_derive_raw_spans`):

1. Single snapshot with one value → one still-open span clipped to `to`.
2. Two snapshots with identical value → one long span.
3. Two snapshots with different values for same path → two back-to-back spans.
4. Snapshot with explicit closure → span ends at closure time.
5. Cascading closure: parent path closes all open descendants in same source.
6. Cascading closure does **not** affect other sources (source scoping).
7. Close-and-reopen in same snapshot: one span ending, one span starting at same time.
8. Collection-gap case: source goes silent for several snapshots with other sources
   active, then resumes. No spurious close/reopen for the silent source's keys.
9. Consecutive identical-value snapshots collapse into one span (daily heartbeat case).
10. Multi-source conflict on same path: most-recent-wins, warning logged.
11. Synthetic intermediates: only leaf is pushed, tree building emits ancestor groups.
12. Left-edge clipping: span started before `from` → clipped, `meta-span-clipped-left`.
13. Right-edge clipping distinct cases: `meta-span-open` vs `meta-span-clipped-right`
    vs `meta-span-closed` (exhaust all end-reason × position combinations).
14. Empty asset (no snapshots): returns `{groups: [], items: []}`.
15. Path with only trailing whitespace (`["  "]`): rejected at Pydantic validation,
    not at derivation. Derivation unit tests assume clean input.
16. **`closed`-only snapshot terminates an existing span.** Setup: push a `values`-only
    snapshot opening `["legacy-plugin"]` at T0. Push a second snapshot at T1 with
    `values: []` and `closed: [{path: ["legacy-plugin"]}]`. Expected: one emitted
    span with `start=T0`, `end=T1`, `end_reason="closed"`, `meta-span-closed` class.
17. **`closed`-only snapshot targeting an already-closed path is a no-op.** Setup:
    push `values`-only opening `["foo"]` at T0, `closed`-only closing `["foo"]` at
    T1, then another `closed`-only closing `["foo"]` again at T2. Expected: exactly
    one emitted span `[T0, T1]` with `end_reason="closed"`. The T2 closure is
    silently ignored during derivation; no stray span, no error.
18. **`closed`-only snapshot targeting a path that was never opened is a no-op.**
    Setup: push `closed`-only `{path: ["never-existed"]}` at T0 on an asset with no
    prior snapshots. Expected: derivation emits zero spans for that path. No error.
    The snapshot row and closure row still exist in the database (§5.3 write
    semantics are additive regardless of whether anything matches at read time).
19. **`closed`-only cascading works.** Setup: push `values`-only opening
    `[["app-A"], ["app-A", "plugin-1"], ["app-A", "plugin-2"]]` at T0 from source
    `cicd`. Push `closed`-only `{path: ["app-A"]}` at T1 from the same source.
    Expected: three emitted spans, all with `end=T1`, `end_reason="closed"`, one per
    path.

Each test case is a small fixture of snapshots → expected `groups` + `items` output,
compared structurally.

### 10.2 Integration tests (DB + API)

Live in `api/tests/db/test_asset_meta_ingest_and_read.py`, marked
`@pytest.mark.integration`. Cover:

1. Round-trip: POST a snapshot, GET the timeline, assert the span shows up.
2. Validation: each Pydantic rule enforced (empty path, too-deep path, empty snapshot,
   duplicate paths in same request, invalid source pattern, malformed datetime).
3. Asset-not-found returns 404 on all three endpoints (POST, GET timeline, GET
   summary).
4. Multi-source: two sources push to same asset, timeline contains data from both.
5. Cascading closure: push app + plugins, then close parent, GET confirms all children
   ended at closure time.
6. Large snapshot (500 values) round-trips without error.
7. Window clipping: pushes span [−60d, +10d] then GET with window [−30d, now]; assert
   span is clipped-left and open-right in response.
8. **Closed-only snapshot round-trip**: push values-only to open a span, push
   closed-only to terminate it, GET confirms the span ended at the closure time
   with `meta-span-closed` class.
9. **Summary endpoint**: push 3 distinct-path snapshots, GET the summary, assert
   `{itemCount: 3}`. Push one more snapshot on a fourth path, GET again, assert
   `{itemCount: 4}`.
10. **Summary/timeline count parity**: for several fixtures, assert that
    `summary.itemCount == len({tuple(item.path) for item in timeline.items with
    distinct paths})` — the collapsed strip and the expanded timeline never
    disagree about how many things are tracked.

### 10.3 UI component tests

Live alongside the components as `*.test.tsx`, using Vitest + React Testing Library +
happy-dom per the existing UI testing guide in CLAUDE.md.

1. `MetaTimelineSection.test.tsx`:
   - Default collapsed (timeline container not in DOM; only the single-row
     `CollapsedStrip` rendered).
   - Summary query runs on mount; item count appears in the strip.
   - Click strip → `isExpanded` flips, full-data query fires, timeline container
     appears in DOM.
   - Click strip again → collapses back to single row.
   - Empty response → empty state copy visible when expanded.
   - Error response → error state copy visible when expanded.
   - Height when collapsed is ≤ 40px (measured via `getBoundingClientRect`).
2. `CollapsedStrip.test.tsx`:
   - Zero items → "no items tracked".
   - One item → "1 item tracked" (singular).
   - Many items → "N items tracked".
   - `aria-expanded` reflects `expanded` prop.
   - Click fires `onToggle`.
   - Investigation hint visible only when collapsed, not when expanded.
2. `MetaTimeline.test.tsx` — this one is awkward because vis-timeline manipulates the
   DOM imperatively and happy-dom does not render the timeline faithfully. Scope:
   - On mount, the `<div>` container ref is bound.
   - On unmount, no errors (destroy cleanup runs).
   - Re-render with new items updates the DataSet (test by spying on `clear` / `add`
     through a jest.fn wrapped DataSet, or by checking that the wrapper's
     `itemsDataSetRef` is invoked).
   - **Do not** attempt to assert pixel-level rendering — vis-timeline is an escape
     hatch out of the DOM testing layer. That is verified manually during development.
3. `renderSpanTooltip.test.tsx`:
   - Each class combination produces the expected annotations on the "To:" line.
   - HTML escaping works for values with `<`, `>`, `&`.

### 10.4 Manual verification checklist

(For the PR review checklist — not an automated test.)

- [ ] The Gantt renders inside the eval detail page.
- [ ] The focus-eval marker is positioned exactly at the eval's `period_end`.
- [ ] The marker cannot be dragged.
- [ ] Hovering a span shows the rich tooltip with key, value, from, to, duration.
- [ ] Clicking the parent group chevron expands / collapses children.
- [ ] Spans that started before the window show a dashed left edge.
- [ ] Open-ended spans (no closure) show a faded right edge.
- [ ] Closed spans show a solid right cap.
- [ ] The section collapses and re-expands cleanly without console errors.
- [ ] Theme switch (dark ↔ current) re-styles spans and marker without re-mount glitches.

---

## 11. Open questions for implementation

These are intentionally unresolved at spec time — they are judgment calls best made in
the PR rather than pre-committed to here. Flagging so the implementer knows to surface
them:

1. **Exact color choices** for `meta-span` and `meta-span-closed` across dark / current /
   light themes. The design uses semantic tokens (`--color-meta-span-bg`) but the concrete
   values are a design decision during implementation. Coordinate with the existing theme
   system in `ui/src/index.css`.
2. **Tooltip date format** — `Mar 17 2026, 14:32 UTC` vs `2026-03-17 14:32 UTC` vs
   locale-aware. Pick what matches the rest of TROPEK's eval detail formatting.
3. **Fixed height of 340 px vs content-sized.** The spec prescribes 340 px for
   predictability. If real usage shows it clips badly for assets with many top-level
   parents, convert to `autoResize: true` + `maxHeight: 480`.
4. **Error copy and empty-state copy.** Write once, use throughout — should be
   consistent with the app's copy tone. The spec prescribes placeholder strings; polish
   them during implementation.
5. **Database migration tool.** Use `just` recipe `scripts/db-regen-migrations.sh` per
   project convention — do **not** hand-write the migration file.

---

## 12. Phase 2+ extensions (non-binding, for context)

These are not part of Phase 1 and no implementation work should be done on them. They
are listed so the Phase 1 implementer can avoid making Phase 2 harder by accident:

- **Per-run pins on the focus-eval marker column.** A second read endpoint returns
  eval-scoped tags (feature flag overrides, `--flag=true` CLI args, on-the-day
  annotations) to be rendered as small icons on the focus marker. Requires no data-
  model change on our side — eval annotations already exist.
- **Staleness visual.** A trailing-edge gradient fade that intensifies based on "days
  since the owning source last confirmed this key". Data already available; purely
  rendering.
- **Multi-asset overlay.** A mode where two assets' timelines are overlaid with distinct
  hue families. Uses the same read endpoint twice and re-groups client-side.
- **Diff view.** "What changed between eval A and eval B?" — a compact tabular
  presentation derived from the same clipped spans, not rendered in the Gantt.
- **Asset-level dashboard page.** The big per-asset Gantt from the original draft spec.
  Consumes the same read endpoint with a wider default window and toolbar controls.
- **Most-recent-source-wins visual treatment** when two sources overlap on a path.
  Today: warning logged, winner shown. Phase 2: multi-color bar or dual row.
- **Client-pushed `Idempotency-Key` header** for ingestion deduplication.
- **Retention policy / archival** for old snapshots.

---

## 13. Migration notes

### 13.1 Database

- This feature adds three new tables. No existing table is modified.
- **SQLAlchemy ORM models** for `AssetMetaSnapshot`, `AssetMetaValue`, and
  `AssetMetaClosure` must be added to `api/tropek/db/models.py` first, matching the
  DDL in §4.1 exactly (`TEXT[]` → `ARRAY(Text)`, UUID PKs, FK cascade, indexes).
- **Never hand-write the Alembic migration.** Once the ORM models are in place, run
  `scripts/db-regen-migrations.sh` per the project's memory rule. That script
  regenerates the migration from the current ORM state against the dev database.
- No data backfill is needed — the feature is green-field.
- For integration tests: after running migrations in the test database
  (`just migrate-test`), the new tables will exist in the test environment as well.
  No special fixtures are needed — integration tests create their own snapshots as
  part of their round-trip assertions.

### 13.2 UI dependency

- Add `vis-timeline` to the UI's `package.json`. Install with `pnpm add vis-timeline`
  in the `ui/` directory. Pin to the currently-latest v8.x — at spec-write time this
  is v8.5.0, dual Apache-2.0 / MIT licensed.
- vis-timeline ships its own TypeScript types; no separate `@types/vis-timeline`
  package is needed.
- Import the CSS stylesheet in `MetaTimeline.tsx`: `import "vis-timeline/styles/vis-timeline-graph2d.min.css"`.
  This brings in the default vis styles that our `.vis-item.meta-span` rules extend.
- No new peer dependencies or Vite plugins are required.

### 13.3 Deployment

Deployment is a single migration + API + UI build. No coordinated cross-service
rollout required. Clients of the existing API are unaffected — all new endpoints live
under a new route prefix and new tables live in new schemas.

---

## 14. Acceptance criteria (Phase 1 done when)

1. New tables exist and are reachable via the repositories layer.
2. `POST /assets/{id}/meta/snapshots` accepts the documented contract, validates all
   rules in §5.2, and inserts rows transactionally.
3. `GET /assets/{id}/meta/timeline?from=&to=` returns vis-timeline-shaped JSON per §6.3.
4. `GET /assets/{id}/meta/timeline/summary?from=&to=` returns `{itemCount: N}` per §6.7.
5. Unit tests for the derivation, conflict, clipping, tree-building, and item-emitter
   functions cover all cases in §10.1 per-function table and pass.
6. Integration tests in §10.2 pass against a real TimescaleDB.
7. UI shows `MetaTimelineSection` as a single-row collapsed strip between the
   heatmap and the first table in the eval detail page.
8. The collapsed strip shows `Asset meta · N items tracked · click to investigate…`
   where N comes from the summary endpoint.
9. Clicking the strip expands it in place; the full timeline query is only fetched
   on first expansion and cached thereafter.
10. The focus-eval marker is pinned, non-draggable, labelled.
11. Nested groups expand/collapse on chevron click with children visible only when
    expanded, parent's own bar always visible.
10. Theme switch works without re-mount artifacts.
11. Manual checklist in §10.4 passes.
12. Existing `docs/meta-gantt/asset_version_gantt_spec.docx` is left in place but marked
    as superseded by this document.
