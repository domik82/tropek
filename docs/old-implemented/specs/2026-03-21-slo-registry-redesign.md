# SLO Registry Redesign — Datasource, SLI & Unified Tags/Variables

**Date:** 2026-03-21
**Status:** Draft
**Scope:** UI redesign of SLO Registry page + backend tags/variables unification
**Depends on:** Test Coverage Backfill (2026-03-21) — must land first
**Blocks:** DB Normalization + Redis Caching (2026-03-20) — Phase 1 backend should land before DB norm

## Implementation Phasing

This spec is split into two phases to avoid conflicts with the DB Normalization work:

**Phase 1 — Backend (do AFTER test backfill, BEFORE DB normalization):**
- Tags/variables rename across all models, schemas, repositories
- New `token` field on Datasource
- New `variables` field on Asset, SLO Definition
- `DELETE /datasources/{name}` endpoint
- Tag filtering endpoints on all entities (`tag-keys`, `tag-values`, query params)
- Worker variable resolution rewrite
- Client library + bootstrap manifest updates
- Run `db-regen-migrations.sh` to squash

**Phase 2 — UI (do IN PARALLEL with or AFTER DB normalization):**
- Sidebar-driven navigation (By Asset / By SLO / By Datasource modes)
- Datasource CRUD UI with token handling
- SLI Definition management UI (nested under datasources)
- SLO creation wizard with progressive disclosure
- Structured criteria input (operator/sign/value/% dropdowns)
- Universal search + tag filter bar
- Searchable comboboxes replacing native `<select>` elements
- Binding chain visualization in main panel

Phase 2 is purely frontend — zero backend overlap with DB normalization.

## Problem

The SLO Registry page only manages SLO definitions. Datasources and SLI definitions
have fully built APIs but zero UI. Users cannot create, view, or manage datasources or
SLI definitions without bootstrap YAML manifests. Additionally, the metadata fields
(`labels` on some entities, `meta` on others) conflate descriptive tags with variable
bindings used for query substitution, causing confusion at scale.

## Design Decisions

All decisions below were validated during brainstorming.

### Navigation & Layout

- **Single page, no new nav entries.** Everything stays under the "SLOs" top nav item.
- **Sidebar-driven navigation** with three modes via segmented control:
  - **By Asset:** asset group → asset tree. Click asset → main panel shows SLO bindings.
  - **By SLO:** flat SLO definition list. Click SLO → definition detail + linked assets.
  - **By Datasource:** datasource list (expandable) with nested SLI definitions as
    children (since SLIs are scoped to an adapter_type which maps to a datasource).
- **Prominent Create button** at top of sidebar — full-width, min-height 36px, opens a
  dropdown menu: New Datasource / New SLI Definition / New SLO / New Asset Group.
  Color-coded icons per entity type (blue DS, purple SLI, green SLO, neutral group).
- **Main panel** shows detail for the selected sidebar item. When viewing a linked entity,
  a binding chain breadcrumb is always visible at top.

### Sidebar Filtering (Scalability)

Every sidebar list and every form dropdown gets a universal filter bar:

- **Search input** — free-text, matches name/display_name.
- **Tag filter** — active tag pills with `×` to remove. Add tags via combobox showing
  existing tag keys/values from the dataset. Multiple tags = AND filter.

This is mandatory for large-scale deployments (30+ SLI definitions, 600+ SLOs). Form
dropdowns (SLI picker, SLO picker) become searchable comboboxes with tag filtering
instead of native `<select>` elements.

### Tags vs Variables Unification

Two explicit fields replace the inconsistent `labels`/`meta` naming:

| Field | Type | Purpose |
|-------|------|---------|
| `tags` | `dict[str, str]` | Descriptive, filterable, for humans (team, env, tier) |
| `variables` | `dict[str, str]` | Substitution bindings, used at evaluation time |

Which entities get which:

| Entity | `tags` | `variables` |
|--------|:---:|:---:|
| Datasource | yes | no |
| SLI Definition | yes | no |
| SLO Definition | yes | yes (`$aggregation_window`, etc.) |
| Asset | yes | yes (`$job`, `$namespace`, `$instance`) |
| Evaluation | no | yes (`$branch`, per-run overrides) |
| Annotation | yes | no |

Variable merge order at evaluation time (highest priority first):

```
evaluation.variables  →  slo.variables  →  asset.variables  →  reserved ($asset_name, $start, $end)
```

Implementation: `build_variables()` starts with reserved, then merges asset, slo, and
evaluation using `setdefault` — later sources (higher priority) are merged first so
their values take precedence. This matches the existing `setdefault` pattern in
`worker.py`.

### Datasource Management

**Read view (main panel):**
- Header: display_name + name (monospace)
- Fields: adapter_type (badge), adapter_url (monospace), token (masked `••••••••` with
  eye toggle showing existence only, never actual value), tags (pills)
- "Used by" section: SLI definitions sharing the same adapter_type (clickable)
- Actions: Edit | Delete (with confirmation — reject with 409 if active SLO links
  reference this datasource; show affected links in confirmation dialog)

**Create/Edit form:**
- Progressive disclosure:
  1. Identity — name (slug), display_name, adapter_type dropdown
  2. Connection — adapter_url (monospace), token (password field with eye toggle, only
     sent on save if non-empty)
- Tags: key-value row editor

**Token handling:**
- Create: plain text input
- Edit: shows `••••••••` placeholder, only updates if user types new value
- Read/list: eye icon toggles between `••••••••` and empty (existence check, never value)
- API never returns token on GET

### SLI Definition Management

**Sidebar placement:** nested under datasources in "By Datasource" mode.

```
▼ prometheus-local          [prometheus]
    http-service-sli        3 indicators
    db-sli                  2 indicators
▶ mock-dc-b                [mock]
```

**Read view (main panel):**
- Header: display_name + name + version badge + active/inactive status
- Adapter type badge
- Indicators table: `Name` | `Query Template` (monospace, `$variables` highlighted)
- Tags, notes, author
- "Used by" section: SLO definitions referencing these indicators (clickable)
- Version history (expandable, same pattern as current SLO history)
- Actions: New Version | Deactivate

**Create/Edit form:**
- Progressive disclosure:
  1. Identity — name (slug), display_name, adapter_type (pre-filled from DS context),
     author, notes
  2. Indicators — key-value row editor:
     - Each row: indicator name (text) + query template (monospace input)
     - `+ Add indicator` button
     - Help text: reserved variables (`$asset_name`, `$evaluation_name`, `$start`, `$end`)
     - Hint: "Asset and SLO variables ($job, $aggregation_window) are substituted at
       evaluation time"
- Tags: key-value row editor
- New version pre-fills form with current values

### SLO Definition — Redesigned Creation Wizard

Progressive disclosure form — sections unfold as you fill them. No "Next" buttons.

**Step 1: Identity**
- Name (slug), display_name, author, notes
- Once name is filled → Step 2 appears

**Step 2: Pick Datasource & SLI**
- 2a: Datasource dropdown (small list) — **UI filter only**, not stored on the SLO
  definition. Narrows the SLI list. The datasource is captured later when the SLO is
  linked to an asset group via the SLO Link dialog.
- 2b: SLI Definition — searchable combobox filtered by adapter_type, with tag filter
- Once SLI selected → Step 3 appears showing available indicators

**Step 3: Pick Indicators & Set Thresholds**
- All indicators from the selected SLI appear as rows with a checkbox
- Unchecked = skipped (dimmed)
- Checked rows show threshold inputs with structured criteria controls:
  - **Operator dropdown:** `<`, `<=`, `>`, `>=`, `=`
  - **Sign dropdown:** `+`, `-`, none (none = fixed threshold)
  - **Value input:** numeric
  - **% toggle button:** on = percentage (relative to baseline), off = absolute
  - Multiple criteria per objective via `+ Add criterion`
- Weight: number input (default 1)
- Key SLI: checkbox
- Once at least one indicator checked with pass criteria → Step 4 appears

**Step 4: Comparison & Score Thresholds**
- Compare with: `single_result` | `several_results`
- Number of comparison results
- Include results with score: `pass` | `pass_or_warn` | `all`
- Aggregate function: `avg` | `p50` | `p90` | `p95` | `p99`
- Total pass % (default 90), total warning % (default 75)
- SLO-level variables: key-value row editor (`$aggregation_window` etc.)
- Tags: key-value row editor

**Footer:** Cancel | Create SLO (enabled when all required fields valid)

**Supported criteria formats (from engine):**

| Example | Operator | Sign | Value | % | Type |
|---------|:---:|:---:|:---:|:---:|------|
| `<600` | `<` | — | 600 | off | Fixed threshold |
| `<=+10%` | `<=` | `+` | 10 | on | Relative percent (baseline + 10%) |
| `>=-5%` | `>=` | `-` | 5 | on | Relative percent (baseline − 5%) |
| `<=+50` | `<=` | `+` | 50 | off | Relative absolute (baseline + 50) |

### Binding Chain View

**Main panel when an asset is selected (By Asset mode):**

SLO bindings are **inherited from the asset's parent group(s)**, not direct asset-SLO
links (asset-level links are out of scope). The UI resolves which groups the asset
belongs to and aggregates their SLO links. Each binding is shown as a card:

- Chain breadcrumb: `http-availability-slo v3.1 → http-service-sli → prometheus-local`
- Variable resolution panel showing merged sources:
  - `asset.variables:` $job=checkout, $namespace=prod
  - `slo.variables:` $aggregation_window=5m
  - `reserved:` $asset_name, $start, $end
- Objectives table with structured criteria display
- Actions: Edit Link | Test SLO | Unlink

Empty state: "Link an SLO" button → opens link dialog.

**SLO Link dialog (revised cascade):**
1. Pick Datasource (dropdown)
2. Pick SLI Definition (searchable combobox, filtered by adapter_type, tag-filterable)
3. Pick SLO Definition (searchable combobox, tag-filterable)
4. Confirm → creates link

**Cross-entity navigation:**
- All entity references are clickable links that switch sidebar mode and select the item
- DS detail → shows linked SLIs
- SLI detail → shows SLOs referencing its indicators
- SLO detail → shows linked assets/groups

## Backend Changes

### Schema Renames

All modules:

| Entity | Old field | New field |
|--------|-----------|-----------|
| Datasource | `labels` | `tags` |
| SLI Definition | `meta` | `tags` |
| SLO Definition | `meta` | `tags` |
| Asset | `labels` | `tags` |
| Annotation (in `quality_gate/schemas.py`) | `meta` | `tags` |
| Evaluation | `evaluation_metadata` | `variables` (rename for clarity) |
| TriggerRequest | `metadata` | `variables` |
| BatchTriggerRequest | `metadata` | `variables` |

### New Fields

| Entity | Field | Type | Purpose |
|--------|-------|------|---------|
| Datasource | `token` | `str` (nullable, write-only) | Adapter auth token. Never returned on GET. Stored encrypted. |
| Asset | `variables` | `dict[str, str]` | Identity bindings ($job, $namespace) |
| SLO Definition | `variables` | `dict[str, str]` | SLO-scoped bindings ($aggregation_window) |
| Evaluation | keep `variables` | `dict[str, str]` | Per-run overrides ($branch) |

### New Endpoints

- `DELETE /datasources/{name}` — delete datasource. Returns 409 if active SLO links
  reference it.

### API Field Renames (Breaking)

The `TriggerRequest.metadata` and `BatchTriggerRequest.metadata` fields are renamed to
`variables` for consistency. This is a breaking API change — the old field name is not
aliased.

### Tag Filtering on All Entities

Add `tag_key` + `tag_val` query params to:
- `GET /datasources`
- `GET /sli-definitions`
- `GET /slo-definitions`

Add tag discovery endpoints (same pattern as existing `/assets/label-keys`):
- `GET /datasources/tag-keys` + `GET /datasources/tag-values?key=X`
- `GET /sli-definitions/tag-keys` + `GET /sli-definitions/tag-values?key=X`
- `GET /slo-definitions/tag-keys` + `GET /slo-definitions/tag-values?key=X`

### Worker Variable Resolution Update

Update `worker.py` variable resolution to merge from the new fields:

```python
# Build base from reserved values
variables = build_variables(
    metadata={},  # no longer pass eval metadata here
    asset_name=asset_snapshot.get("name"),
    evaluation_name=ev.evaluation_name,
    start=ev.period_start.isoformat(),
    end=ev.period_end.isoformat(),
)
# Merge in priority order (setdefault = lower priority, so merge lowest first)
for k, v in (asset_snapshot.get("variables") or {}).items():
    variables.setdefault(k, str(v))
for k, v in (slo_def.variables or {}).items():
    variables[k] = str(v)  # slo overrides asset
for k, v in (ev.variables or {}).items():
    variables[k] = str(v)  # eval overrides everything
```

Instead of current pattern that reads from `asset_snapshot.get("tags")` and
`evaluation_metadata`.

### Client Library Updates

`clients/python/tropek_client/`:
- `models.py` — rename `labels`→`tags`, add `variables` where applicable
- `manifest.py` — update YAML field mapping
- `client.py` — update method signatures
- Tests — update accordingly

### Bootstrap Mock Manifests

`bootstrap_mock/manifests/`:
- `datasources.yaml` — rename `labels:` → `tags:`
- `assets.yaml` — split current `labels:` into `tags:` (descriptive) + `variables:`
  (substitution bindings). Mapping: `job`, `namespace`, `instance`, `runtime`, `os`,
  `dc` → `variables`; `team`, `env`, `region`, `tier` → `tags`.
- `sli-definitions.yaml` — rename `meta:` → `tags:` (if any meta exists)
- `slo-definitions.yaml` — rename `meta:` → `tags:`, add `variables:` where applicable
- `datasources.yaml` — no `token` in bootstrap manifests (tokens should be injected via
  env vars or secrets management, not committed to YAML files)

### Migration

Use `scripts/db-regen-migrations.sh` to squash into single migration after model
changes. No incremental migration files.

### Dev Startup

`scripts/dev-start.sh` — no structural changes needed. It calls `bootstrap.py` which
reads the updated manifests. The field renames flow through automatically once the
client library and manifests are updated.

## Out of Scope

- Asset-level SLO links (current: group-level only) — future work
- SLO test/dry-run button wiring — noted but separate from this redesign
- Adapter management (creating new adapter types) — adapter_type is a free-text string
- Penpot design updates — will be done as a follow-up after spec approval

## Conceptual Documentation

The entity pipeline diagram and data model overview created during brainstorming
(in `.superpowers/brainstorm/`) should be adapted into a `docs/concepts/` guide once
all pieces are implemented. This is a post-implementation task.
