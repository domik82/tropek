# Change Point Config Redesign

**Date:** 2026-04-25
**Status:** Draft

## Problem

The current change point detection configuration has three issues:

1. **Directionality is guessed from criteria strings.** The `directionality.py` module
   infers `higher_is_better` from `pass_threshold` operators, but multi-criteria thresholds
   like `[">0", "<500"]` break the heuristic — the `>0` lower-bound guard causes the
   detector to classify latency increases as improvements.

2. **Config is not version-aware.** `change_point_config` is keyed by `(slo_name, metric_name)`
   strings. It is not tied to a specific SLO version, so config drifts across versions.

3. **Defaults are hardcoded.** Detection defaults (`window_size=30`, `max_pvalue=0.001`, etc.)
   are Python constants. Deployers cannot change them without code changes, and they are lost
   on backup/restore.

## Design

### 1. `configuration` table — system-wide key-value settings

A general-purpose settings table. Change point defaults are the first tenant; other
features will use it later.

```
configuration
├── name         TEXT  PRIMARY KEY
├── value        TEXT  NOT NULL
├── value_type   TEXT  NOT NULL   -- 'bool', 'int', 'float', 'str'
├── description  TEXT  NOT NULL   DEFAULT ''
├── created_at   TIMESTAMPTZ
└── updated_at   TIMESTAMPTZ
```

**Seed rows** (inserted by migration):

| name | value | value_type | description |
|------|-------|------------|-------------|
| `change_point.enabled` | `true` | bool | Enable change point detection globally |
| `change_point.higher_is_better` | `false` | bool | Default metric polarity (false = lower is better) |
| `change_point.window_size` | `30` | int | E-Divisive sliding window length |
| `change_point.max_pvalue` | `0.001` | float | Significance threshold for t-test |
| `change_point.min_magnitude` | `0.0` | float | Minimum relative change to report |
| `change_point.min_sample_size` | `10` | int | Minimum history length for detection |

**API:**

- `GET /configuration` — returns all rows
- `GET /configuration/{name}` — returns single row
- `PUT /configuration/{name}` — update value (validates against `value_type`)

The hardcoded constants in `detector.py` become fallback-only — used if the DB row is
missing (fresh install before seed runs). The resolver reads from `configuration` first.

### 2. `change_point_config` table — re-keyed to `slo_objective_id`

Drop the current `(slo_name, metric_name)` key. Re-key to `slo_objective_id` FK pointing
at `slo_objectives.id`. Add `higher_is_better`. This is alpha software with no production
data to migrate — the table is recreated clean.

```
change_point_config
├── id                 UUID  PRIMARY KEY
├── slo_objective_id   UUID  NOT NULL  FK → slo_objectives.id  UNIQUE
├── enabled            BOOL  NOT NULL
├── higher_is_better   BOOL  NOT NULL
├── window_size        INT   NOT NULL
├── max_pvalue         FLOAT NOT NULL
├── min_magnitude      FLOAT NOT NULL
├── min_sample_size    INT   NOT NULL
├── created_at         TIMESTAMPTZ
└── updated_at         TIMESTAMPTZ
```

The unique constraint on `slo_objective_id` enforces one config per objective.
No server defaults on the columns — values are always explicitly set (either from the
SLO YAML `change_point:` block or copied from the previous version).

**Relationship:** `SLOObjective` gets a `change_point_config` relationship
(`uselist=False`, lazy `joined` or `selectin`) so it is always available when the
objective is loaded.

### 3. SLO YAML `change_point:` block

The SLO objective definition gains an optional `change_point` block:

```yaml
objectives:
  - sli: error_rate
    pass_threshold: ["<0.01"]
    weight: 2
    change_point:
      higher_is_better: false
      window_size: 60
      min_sample_size: 20
```

All fields inside `change_point:` are optional. Missing fields are filled from the
`configuration` table defaults at SLO creation time. If the entire `change_point:` block
is absent, no config row is created for that objective — detection uses system defaults
at runtime.

**Schema changes:**

- `SLOObjectiveIn` (API request) gains `change_point: ChangePointConfigInput | None = None`
- `SLOObjectiveRead` (API response) gains `change_point: ChangePointConfigRead | None = None`
- `SLOObjectiveParams` (internal params) gains `change_point: ChangePointConfigInput | None = None`

```python
class ChangePointConfigInput(StrictInput):
    enabled: bool | None = None
    higher_is_better: bool | None = None
    window_size: int | None = None
    max_pvalue: float | None = None
    min_magnitude: float | None = None
    min_sample_size: int | None = None
```

### 4. Copy-forward on new SLO version

When `SLORepository.create()` inserts a new version of an existing SLO:

1. Load the previous version's objectives with their `change_point_config` relationships.
2. Build a lookup: `{sli_name: ChangePointConfig}` from the previous version.
3. For each new objective:
   - If the new params include a `change_point:` block → use it (merge with system
     defaults for any missing fields).
   - If no `change_point:` block but the previous version had config for this SLI →
     copy the previous config row (all fields).
   - If neither → no config row; detection uses system defaults at runtime.

This ensures config carries forward across versions unless explicitly changed or removed.

### 5. Config resolution in the worker step

The `_detect_for_metric` function currently calls `resolve_configs_for_metrics()` which
queries by `(slo_name, metric_name)`. After the redesign:

1. The worker step already has the `SLODefinition` with eagerly-loaded `objectives`.
2. Each objective's `change_point_config` relationship is loaded (joined/selectin).
3. If `objective.change_point_config` exists → use it directly.
4. If not → read system defaults from the `configuration` table (cached per worker run).
5. Fallback → hardcoded constants (safety net).

The `resolve_configs_for_metrics()` method and the `ResolvedConfig` model stay, but the
resolution source changes from a flat table query to the objective relationship + system
defaults.

`higher_is_better` is read from the config (per-objective or system default) instead of
being guessed from `pass_threshold`. The `directionality.py` module is deleted.

### 6. Per-objective config API (mutable without new SLO version)

Change point config is editable on the fly — it does not require creating a new SLO version.

- `GET /change-points/config/{objective_id}` — resolved config (merged with defaults)
- `PUT /change-points/config/{objective_id}` — create or update config for an objective
- `DELETE /change-points/config/{objective_id}` — remove override, fall back to defaults

The existing `GET /change-points/config/defaults` endpoint is removed — system defaults
are served by `GET /configuration?prefix=change_point`.

### 7. Deletions

- **`directionality.py`** — deleted entirely. All tests in `test_directionality.py` deleted.
- **`detector.py` constants** — `DEFAULT_ENABLED`, `DEFAULT_WINDOW_SIZE`, etc. remain as
  hardcoded fallbacks but are no longer the primary source. The `configuration` table is
  the source of truth.
- **`higher_is_better` column on `slo_objectives`** — revert the column added earlier in
  this session. It belongs in `change_point_config`, not on the objective.
- **Config API endpoints keyed by `(slo_name, metric_name)`** — replaced by
  `{objective_id}` endpoints.

### 8. Client library and bootstrap

- `tropek_client.models.SLOObjective` gains `change_point: dict | None = None`.
- Bootstrap YAML manifests are updated to include `change_point:` blocks where needed
  (at minimum `higher_is_better` for metrics where the default of `false` is wrong, e.g.
  `availability` with `pass_threshold: [">=0.999"]` needs `higher_is_better: true`).

### 9. Files affected

| File | Change |
|------|--------|
| `api/tropek/db/models.py` | Re-key `ChangePointConfig` to `slo_objective_id` FK, add `higher_is_better`, add `Configuration` model, add relationship on `SLOObjective`, revert `higher_is_better` from `SLOObjective` |
| `api/tropek/modules/change_points/repository.py` | Update queries to use `slo_objective_id`, update resolution to read from `configuration` table |
| `api/tropek/modules/change_points/router.py` | Re-key config endpoints to `{objective_id}`, remove `/config/defaults`, add `/configuration` endpoints (or new router) |
| `api/tropek/modules/change_points/schemas.py` | Update config schemas, add `ChangePointConfigInput` |
| `api/tropek/modules/change_points/worker_step.py` | Read config from objective relationship, remove `directionality` import |
| `api/tropek/modules/change_points/directionality.py` | Delete |
| `api/tropek/modules/change_points/detector.py` | Keep constants as fallbacks only |
| `api/tropek/modules/slo_registry/params.py` | Add `change_point` field to `SLOObjectiveParams`, revert `higher_is_better` |
| `api/tropek/modules/slo_registry/schemas.py` | Add `change_point` to `SLOObjectiveIn` and `SLOObjectiveRead` |
| `api/tropek/modules/slo_registry/repository.py` | Insert `change_point_config` rows during `create()`, copy-forward logic, revert `higher_is_better` |
| `api/tropek/modules/configuration/` | New module: `models.py` (if separate), `repository.py`, `router.py`, `schemas.py` |
| `api/tests/change_points/test_directionality.py` | Delete |
| `api/tests/change_points/test_worker_step.py` | Update mocks for new config resolution |
| `clients/python/tropek_client/models.py` | Add `change_point` to `SLOObjective` |
| `bootstrap_mock/manifests/slo-definitions.yaml` | Add `change_point:` blocks with `higher_is_better` where needed |
| `api/alembic/versions/001_initial_schema.py` | Regenerated |
