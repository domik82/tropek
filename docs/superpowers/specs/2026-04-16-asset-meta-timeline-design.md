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
- A collapsible section in the evaluation detail page that renders the timeline with
  the current evaluation pinned as a non-draggable vertical marker.
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

---

## 7. Server-side algorithms

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

**Step 2 — walk and emit.**

```python
# open_spans maps (source, tuple(path)) -> (value, span_start)
open_spans: dict[tuple[str, tuple[str, ...]], tuple[str, datetime]] = {}
emitted: list[RawSpan] = []

for snapshot in snapshots_ordered_by_observed_at:
    # Apply closures FIRST (so close-and-reopen in same snapshot works).
    for closure_path in snapshot.closures:
        close_cascade(
            open_spans=open_spans,
            source=snapshot.source,
            ancestor=tuple(closure_path),
            closed_at=snapshot.observed_at,
            emitted=emitted,
        )

    # Then apply values.
    for path, value in snapshot.values:
        key = (snapshot.source, tuple(path))
        existing = open_spans.get(key)
        if existing is None:
            open_spans[key] = (value, snapshot.observed_at)
        else:
            existing_value, existing_start = existing
            if existing_value == value:
                pass  # span continues unchanged
            else:
                emitted.append(RawSpan(
                    source=key[0],
                    path=list(key[1]),
                    value=existing_value,
                    start=existing_start,
                    end=snapshot.observed_at,
                    end_reason="value_change",
                ))
                open_spans[key] = (value, snapshot.observed_at)

# After all snapshots are processed, any remaining open_spans are still active.
for (source, path_tuple), (value, start) in open_spans.items():
    emitted.append(RawSpan(
        source=source,
        path=list(path_tuple),
        value=value,
        start=start,
        end=None,  # None == still open at the end of known data
        end_reason="open",
    ))
```

Where `close_cascade` is:

```python
def close_cascade(open_spans, source, ancestor, closed_at, emitted):
    """Close ancestor's span AND every descendant for the same source."""
    to_close = [
        key for key in open_spans
        if key[0] == source and _is_prefix(ancestor, key[1])
    ]
    for key in to_close:
        value, start = open_spans.pop(key)
        emitted.append(RawSpan(
            source=key[0],
            path=list(key[1]),
            value=value,
            start=start,
            end=closed_at,
            end_reason="closed",
        ))


def _is_prefix(prefix: tuple[str, ...], full: tuple[str, ...]) -> bool:
    """True if `prefix` is a prefix of `full` (including equal)."""
    return len(prefix) <= len(full) and full[:len(prefix)] == prefix
```

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
from collections import defaultdict

# Group emitted spans by path. For each path, also record the latest observation
# timestamp per source touching that path, so we can pick the winner.
spans_by_path: dict[tuple[str, ...], list[RawSpan]] = defaultdict(list)
latest_per_source: dict[tuple[str, ...], dict[str, datetime]] = defaultdict(dict)

for span in emitted:
    path_key = tuple(span.path)
    spans_by_path[path_key].append(span)
    # The "latest observation for this (path, source)" is the latest span start OR end
    # (the end of an open span is the query's `to`, which is fine as a sentinel — any
    # source with a live open span at query time has the most recent observation).
    observed_time = span.end if span.end is not None else datetime.max
    current = latest_per_source[path_key].get(span.source, datetime.min)
    latest_per_source[path_key][span.source] = max(current, observed_time)

# Resolve: for each path with >1 source, pick the source with the latest observation,
# drop the others, log a warning.
winning_spans: list[RawSpan] = []
for path_key, spans in spans_by_path.items():
    sources = latest_per_source[path_key]
    if len(sources) == 1:
        winning_spans.extend(spans)
        continue

    winning_source = max(sources.items(), key=lambda kv: (kv[1], kv[0]))[0]
    # ^ primary key: most recent; secondary key: source name (deterministic tie-break)
    logger.warning(
        "asset_meta_timeline.multi_source_conflict",
        extra={
            "asset_id": str(asset_id),
            "path": list(path_key),
            "sources": sorted(sources.keys()),
            "winner": winning_source,
        },
    )
    winning_spans.extend(s for s in spans if s.source == winning_source)

# `winning_spans` replaces `emitted` for downstream clipping and emission.
emitted = winning_spans
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

### 7.3 Window clipping

After raw spans are emitted, clip each span to `[from, to]`:

```python
clipped: list[ClippedSpan] = []
for span in emitted:
    effective_end = span.end if span.end is not None else to
    if effective_end <= from_:
        continue  # entirely before window
    if span.start >= to:
        continue  # entirely after window

    classes = ["meta-span"]
    clipped_start = span.start
    clipped_end = effective_end

    if clipped_start < from_:
        clipped_start = from_
        classes.append("meta-span-clipped-left")

    if span.end is None:
        # Still open at end of known data.
        if clipped_end > to:
            clipped_end = to
        classes.append("meta-span-open")
    elif clipped_end > to:
        clipped_end = to
        classes.append("meta-span-clipped-right")

    if span.end_reason == "closed":
        classes.append("meta-span-closed")

    clipped.append(ClippedSpan(
        source=span.source,
        path=span.path,
        value=span.value,
        start=clipped_start,
        end=clipped_end,
        className=" ".join(classes),
    ))
```

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
# Collect all distinct paths that have at least one clipped span.
distinct_paths: set[tuple[str, ...]] = {tuple(span.path) for span in clipped}

# For each path, walk every prefix and add synthetic intermediates.
all_group_paths: set[tuple[str, ...]] = set()
for path in distinct_paths:
    for i in range(1, len(path) + 1):
        all_group_paths.add(path[:i])

# Compute children for each group.
# A group P has child Q iff len(Q) == len(P) + 1 and Q[:-1] == P.
children_of: dict[tuple[str, ...], list[tuple[str, ...]]] = defaultdict(list)
for p in all_group_paths:
    if len(p) > 1:
        parent = p[:-1]
        children_of[parent].append(p)

# Emit the flat group list, sorted for determinism: by depth ASC, then alphabetically
# on the joined path within a depth. This gives stable diffs in tests.
sorted_groups = sorted(
    all_group_paths,
    key=lambda p: (len(p), p),
)

groups_wire: list[dict] = []
for path in sorted_groups:
    entry = {
        "id": json.dumps(list(path), ensure_ascii=False, separators=(",", ":")),
        "content": path[-1],
    }
    if path in children_of:
        child_paths_sorted = sorted(children_of[path])
        entry["nestedGroups"] = [
            json.dumps(list(cp), ensure_ascii=False, separators=(",", ":"))
            for cp in child_paths_sorted
        ]
        entry["showNested"] = False
    groups_wire.append(entry)
```

**Key point: synthetic intermediates.** If the only path with data is
`["app-A", "plugin-pkg-1", "plugin-alpha"]`, the server synthesizes groups for
`["app-A"]` and `["app-A", "plugin-pkg-1"]`. Both are pure containers (no items will
target them) but they exist as group rows with chevrons so the user can collapse the
subtree. Without synthetics, vis-timeline would have no group for the child to attach
to via `nestedGroups` and would render the leaf as top-level.

### 7.5 Item emission

```python
items_wire: list[dict] = []
for index, span in enumerate(clipped):
    group_id = json.dumps(span.path, ensure_ascii=False, separators=(",", ":"))
    items_wire.append({
        "id": f"s{index}",
        "group": group_id,
        "content": span.value,
        "start": span.start.isoformat(),
        "end":   span.end.isoformat(),
        "type":  "range",
        "className": span.className,
        "source": span.source,
    })
```

Note: vis-timeline passes extra fields through unchanged on `Item` objects and makes
them available inside `tooltip.template(item)`. The `source` field is carried purely
so the tooltip can display it; vis-timeline itself does nothing with it.

### 7.6 Performance and caching

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
├── schemas.py          # Pydantic request/response
├── params.py           # internal parameter objects
├── repositories.py     # DB access (async SQLAlchemy)
├── service.py          # validation + write orchestration
├── derivation.py       # span derivation algorithm (pure, zero I/O)
├── tree_builder.py     # group tree building (pure, zero I/O)
├── router.py           # FastAPI routes
```

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

### 8.3 Service method (sketch)

```python
async def create_meta_snapshot(
    session: AsyncSession,
    asset_id: UUID,
    payload: MetaSnapshotCreate,
) -> MetaSnapshotCreated:
    if not payload.values and not payload.closed:
        raise AssetMetaValidationError("snapshot must contain values or closed")

    # Asset existence check (404 path).
    if not await asset_repo.asset_exists(session, asset_id):
        raise AssetNotFoundError(asset_id)

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

    await session.commit()
    return MetaSnapshotCreated(snapshot_id=snapshot.id)
```

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

  const { data, isLoading, error } = useMetaTimeline(assetId, from, to, {
    enabled: isExpanded,
  })

  return (
    <Card>
      <CardHeader
        onClick={() => setIsExpanded((v) => !v)}
        expanded={isExpanded}
      >
        Asset meta timeline
      </CardHeader>
      {isExpanded && (
        <CardBody>
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
        </CardBody>
      )}
    </Card>
  )
}
```

- **Default collapsed.** Users opt in by clicking. Not every user cares about this row.
- **Query is gated on `isExpanded`.** We only fetch when the user expands the section,
  saving the read for users who actively want it. Subsequent collapse/expand cycles
  reuse the cached query result (standard React Query behavior).
- **`from` / `to` are computed locally.** Asymmetric window: 30 days of history before
  the focus eval, 7 days of trailing context to show open-ended spans leaving the
  current state.

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

Locate the `EvaluationDetail` (or equivalent) component that renders eval details, and
add `<MetaTimelineSection />` below the existing notes section and above any future
trend blocks. The section is a sibling, not nested inside an existing card.

The section is always rendered when an eval is loaded (regardless of data), so users
discover the feature exists even for assets that do not yet have meta pushed.

---

## 10. Testing strategy

### 10.1 Pure unit tests (derivation and tree building)

Live in `api/tests/engine/test_asset_meta_derivation.py` (no DB, no network). Cover:

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
3. Asset-not-found returns 404.
4. Multi-source: two sources push to same asset, timeline contains data from both.
5. Cascading closure: push app + plugins, then close parent, GET confirms all children
   ended at closure time.
6. Large snapshot (500 values) round-trips without error.
7. Window clipping: pushes span [−60d, +10d] then GET with window [−30d, now]; assert
   span is clipped-left and open-right in response.

### 10.3 UI component tests

Live alongside the components as `*.test.tsx`, using Vitest + React Testing Library +
happy-dom per the existing UI testing guide in CLAUDE.md.

1. `MetaTimelineSection.test.tsx`:
   - Default collapsed (timeline container not in DOM).
   - Click header → expands, shows loading state, then the timeline.
   - Empty response → empty state copy visible.
   - Error response → error state copy visible.
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
4. Unit tests for the derivation and tree-building algorithms cover all cases in
   §10.1 and pass.
5. Integration tests in §10.2 pass against a real TimescaleDB.
6. UI shows `MetaTimelineSection` in the eval detail page, default-collapsed.
7. Expanding the section fetches and renders the timeline.
8. The focus-eval marker is pinned, non-draggable, labelled.
9. Nested groups expand/collapse on chevron click with children visible only when
   expanded, parent's own bar always visible.
10. Theme switch works without re-mount artifacts.
11. Manual checklist in §10.4 passes.
12. Existing `docs/meta-gantt/asset_version_gantt_spec.docx` is left in place but marked
    as superseded by this document.
