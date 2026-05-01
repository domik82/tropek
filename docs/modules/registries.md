# SLO & SLI Registries

## Purpose

Versioned, immutable definition registries for SLOs and SLIs. Every change creates a
new version -- evaluations record which version they used, so historical results are
always reproducible.

## Key Concepts

| Concept | What It Is |
|---------|------------|
| **SLO Definition** | Structured objectives with criteria, scoring thresholds, and comparison config. Identified by name + version. |
| **SLI Definition** | A map of metric names to query strings (PromQL, SQL, etc.). Identified by name + version. |
| **Versioning** | Immutable after insert. POST with an existing name auto-increments the version. |
| **Soft Delete** | DELETE deactivates all versions (sets `active = false`). Data is preserved. |
| **Validation** | `POST /slo-definitions/validate` dry-runs SLO parsing and criteria checking without creating a version. |
| **Test** | `POST /slo-definitions/test` evaluates an SLO against live adapter metrics without persisting results. |
| **Tags** | Both SLOs and SLIs support key/value tags for filtering and grouping. |

## Versioning Model

SLO and SLI registries share the same versioning mechanism:

1. **Name-based identity.** Entities are identified by a stable `name` string, not a UUID.
   The UUID is an internal primary key.
2. **Auto-incrementing version.** On create, the repository runs
   `SELECT version ... FOR UPDATE ... LIMIT 1` against all rows with the same name, then
   inserts version N+1. The `FOR UPDATE` lock prevents race conditions when two requests
   try to create the same name concurrently.
3. **`comparable_from_version`.** Tracks from which version baseline comparisons are valid.
   Resolution order: explicit parameter > previous version's value > 1 (for the first version).
   This allows baseline continuity across criteria-only changes while resetting when the
   underlying queries change.
4. **Soft delete.** `DELETE /{name}` sets `active = false` on all versions. Re-POSTing with
   the same name after deletion creates a new active version continuing from the next
   version number.
5. **Latest-version queries.** `list_all()` uses PostgreSQL's `DISTINCT ON (name)` ordered
   by version descending to return exactly one row per name -- the latest active version.
6. **Cache invalidation.** On create, the Redis key `{entity}:{name}:latest` is invalidated
   (e.g., `slo:my-slo:latest`).

## SLI Modes

SLI definitions support two mutually exclusive modes, enforced by a `model_validator` on
`SLIDefinitionCreate`:

| Mode | Required Fields | Disallowed Fields |
|------|-----------------|-------------------|
| **`raw`** (default) | `indicators` (non-empty dict of metric name to query string) | `query_template`, `interval`, `methods` |
| **`aggregated`** | `query_template`, `interval`, `methods` (non-empty list) | `indicators` |

Aggregation methods (`AggregationMethod` enum): min, mean, max, std, sum, median, p75, p90, p95, p99.

## SLO-to-SLI Binding

An SLO definition optionally references an SLI definition via `sli_name` and `sli_version`.
The router resolves these to an `sli_definition_id` FK before passing to the repository.
During SLO creation, the router also validates that every objective's `sli` key exists in
the linked SLI definition's `indicators` map.

The response model (`SLODefinitionRead`) flattens this relationship back into top-level
`sli_name` and `sli_version` fields via a `model_validator(mode='before')`.

## SLO Test Service

`SLOTestService` (in `slo_registry/service.py`) is a stateless orchestrator for dry-run
evaluation. It does not persist any results.

The `run_test()` method executes the full pipeline:

1. Parse the SLO definition via `build_slo()`
2. Resolve SLI definition, datasource, and asset
3. Build template variables from asset tags and variables
4. Query the adapter's `/query` endpoint via HTTP POST
5. Resolve baselines (three modes: `none`, `manual` with user-provided values,
   `asset_history` querying past evaluations via `BaselineRepository`)
6. Call the core `evaluate()` engine function
7. Return `SLOTestResult`

## Typical Workflows

### Create and iterate on an SLO

1. Validate the SLO structure: `POST /slo-definitions/validate`
2. Test against live metrics: `POST /slo-definitions/test`
3. Create version 1: `POST /slo-definitions`
4. Update (creates version 2): `POST /slo-definitions` with the same name
5. View version history: `GET /slo-definitions/{name}/versions`

### Create an SLI definition

1. Create: `POST /sli-definitions` with an indicator map and adapter type
2. Reference from an SLO definition via `sli_name` (and optionally `sli_version`)

## SLO Endpoints

| Method | Path | What It Does |
|--------|------|--------------|
| `GET` | `/slo-definitions` | List all active SLO definitions. Supports `tag_key`, `tag_val`, and `kind` filters. |
| `POST` | `/slo-definitions` | Create a new SLO definition (auto-increments version if name exists). |
| `POST` | `/slo-definitions/validate` | Validate SLO structure and criteria strings without saving. |
| `POST` | `/slo-definitions/test` | Evaluate an SLO against live adapter metrics without persisting. |
| `GET` | `/slo-definitions/tag-keys` | Return distinct tag keys with usage counts. |
| `GET` | `/slo-definitions/tag-values` | Return distinct tag values for a given key with usage counts. |
| `GET` | `/slo-definitions/{name:path}` | Get the latest active version of an SLO definition. |
| `GET` | `/slo-definitions/{name:path}/versions` | List all versions of an SLO definition. |
| `DELETE` | `/slo-definitions/{name:path}` | Deactivate all versions of an SLO definition. |

## SLI Endpoints

| Method | Path | What It Does |
|--------|------|--------------|
| `GET` | `/sli-definitions` | List all active SLI definitions. Supports `adapter_type`, `tag_key`, and `tag_val` filters. |
| `POST` | `/sli-definitions` | Create a new SLI definition (auto-increments version if name exists). |
| `GET` | `/sli-definitions/tag-keys` | Return distinct tag keys with usage counts. |
| `GET` | `/sli-definitions/tag-values` | Return distinct tag values for a given key with usage counts. |
| `GET` | `/sli-definitions/{name}` | Get the latest active version of an SLI definition. |
| `GET` | `/sli-definitions/{name}/versions` | List all versions of an SLI definition. |
| `DELETE` | `/sli-definitions/{name}` | Deactivate all versions of an SLI definition. |

## Assignments

SLO definitions are bound to [assets](assets.md) through assignments. An assignment links
a specific SLO definition version plus a [data source](datasources.md) to an asset or
asset group. Assignments are managed via endpoints on the asset and asset group routers
(see [Assets](assets.md) for details).

### Assignment Resolution (4-Tier Priority)

When an evaluation is triggered for an asset, the system determines which SLOs apply
using a 4-tier priority system. The `resolve_for_asset()` method in `AssignmentRepository`
runs a raw SQL CTE with a `UNION ALL` across four sources:

| Priority | Source | Description |
|----------|--------|-------------|
| 4 (highest) | `direct_asset` | SLO assigned directly to the asset |
| 3 | `direct_group` | SLO assigned to any group the asset belongs to |
| 2 | `template_asset` | Generated SLO from an [SLO group](slo-groups.md) assigned directly to the asset |
| 1 (lowest) | `template_group` | Generated SLO from an SLO group assigned to one of the asset's groups |

`DISTINCT ON (slo_name)` with `CASE source ... END DESC` ordering picks the highest-priority
assignment per SLO concept name. A direct assignment always wins over an inherited or
template-based one.

Each resolved assignment includes: `slo_name`, `slo_definition_id`, `data_source_id`,
`comparison_rules` (from the assignment, not the SLO definition), and `source`.

### Comparison Rules

Comparison rules live on the assignment (not on the SLO definition). They control which
prior evaluations are eligible as baselines for a given evaluation. Rules are defined in
`assets/comparison_rules.py` as a `ComparisonRule` model with two fields:

- **`match`**: tag conditions on the current evaluation's metadata. `{"branch": "main"}` for
  exact match, `{"branch": "!main"}` for negation, `{}` for catch-all.
- **`compare_to`**: tag filters on the baseline query. `{"branch": "main"}` restricts baselines
  to those with `branch=main`. `{"pinned": true}` uses only pinned baselines.

Validation rules: at most one catch-all rule, and it must be last in the list.

Note: the `ComparisonConfig` on the SLO definition itself handles aggregate function and
result filtering. `ComparisonRule` on assignments handles tag-based routing.

## Source Code Layout

```
api/tropek/modules/slo_registry/
    params.py       # SLOCreateParams, SLOObjectiveParams
    repository.py   # SLORepository (versioned CRUD, TagQueryMixin)
    router.py       # FastAPI endpoints
    schemas.py      # SLODefinitionCreate, SLODefinitionRead, ComparisonConfig, etc.
    service.py      # SLOTestService (dry-run evaluation orchestration)

api/tropek/modules/sli_registry/
    params.py       # SLICreateParams
    repository.py   # SLIRepository (versioned CRUD, TagQueryMixin)
    router.py       # FastAPI endpoints
    schemas.py      # SLIDefinitionCreate (mode-dependent validation), SLIDefinitionRead

api/tropek/modules/assignments/
    repository.py   # AssignmentRepository (SLO + SLO group assignment CRUD, resolve_for_asset)
    router.py       # 22 endpoints for assignment management
    schemas.py      # SLOAssignmentUpsert/Read, SLOGroupAssignmentUpsert/Read
```

## Gotchas / Design Decisions

- Versions are auto-incremented using `SELECT ... FOR UPDATE` to prevent race conditions.
- GET returns the latest active version by default. Use `/versions` for full history.
- SLO names support path characters (e.g., `http/api-slo`) via `{name:path}` routing. SLI names do not -- they are plain path segments.
- SLO creation validates that all objective `sli` references exist in the linked SLI definition's indicator map before inserting.
- The `/test` endpoint hits a real adapter (datasource) -- it is not a mock dry-run. It requires a valid datasource to be reachable.
- Deactivation is soft -- re-POSTing with the same name after DELETE creates a new active version starting from the next version number.
- Tag-key and tag-value endpoints enable UI filtering by labels attached to definitions without loading all definitions.
- SLO and SLI registries are structurally near-identical. A base versioned-registry class could reduce duplication but does not exist today.
- The `method_criteria` field on SLO definitions is stored and round-tripped but has no runtime effect -- Level-2 expansion during SLO group generation is not yet implemented.
