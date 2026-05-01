# Configuration Module

## Purpose

Generic key-value configuration store with prefix-scoped queries. Values are stored as
strings with an explicit `value_type` field for typed parsing. Currently used by
change-point detection for system defaults, but designed as a general-purpose facility.
Entries are seeded by migrations, not created at runtime.

## Module Layout

```
api/tropek/modules/configuration/
├── __init__.py       # empty package marker
├── repository.py     # ConfigurationRepository: key-value CRUD with typed parsing
├── router.py         # FastAPI endpoints: list, get, update
└── schemas.py        # Pydantic schemas: ConfigurationRead, ConfigurationUpdate
```

## Repository

`ConfigurationRepository(session)` -- instantiated with an async SQLAlchemy session.

| Method | Parameters | Return | Behavior |
|--------|-----------|--------|----------|
| `get_all()` | `prefix: str?` | `list[Configuration]` | SELECT all rows ORDER BY name. If `prefix` given, filters with `name LIKE 'prefix%'`. |
| `get_by_name()` | `name: str` | `Configuration \| None` | SELECT WHERE name = name. |
| `update_value()` | `name: str, value: str` | `Configuration \| None` | Loads entry by name, validates value against `value_type` using `TYPE_VALIDATORS`, updates value field. Raises `ValueError` on type mismatch. |
| `get_change_point_defaults()` | none | `dict[str, bool\|int\|float\|str]` | Calls `get_all(prefix='change_point.')`, strips prefix, parses each value via `parse_typed_value()`. |

**Type system:** `parse_typed_value()` dispatches on `value_type`: `'bool'` -> lowercase
comparison to `'true'`, `'int'` -> `int()`, `'float'` -> `float()`, else string.
`TYPE_VALIDATORS` rejects invalid input before persisting (e.g. bool accepts only
`'true'`/`'false'` case-insensitively, int requires digits).

## Router & Endpoints

| Method | Path | Parameters | Request Body | Response |
|--------|------|-----------|-------------|----------|
| GET | `/configuration` | `prefix: str?` | -- | `list[ConfigurationRead]` |
| GET | `/configuration/{name:path}` | `name` (path param) | -- | `ConfigurationRead` (404 if missing) |
| PUT | `/configuration/{name:path}` | `name` (path param) | `ConfigurationUpdate` | `ConfigurationRead` (404 if missing, 422 if type invalid) |

**Schemas:**
- `ConfigurationRead`: `name`, `value`, `value_type`, `description`. Uses `from_attributes=True`.
- `ConfigurationUpdate` (StrictInput): `value: str`.

## DB Model

Table: `configuration`

| Column | Type | Constraints |
|--------|------|------------|
| name | Text | PK |
| value | Text | NOT NULL |
| value_type | Text | NOT NULL |
| description | Text | NOT NULL, default `''` |
| created_at | DateTime(tz) | server_default `now()` |
| updated_at | DateTime(tz) | server_default `now()`, onupdate `now()` |

No secondary indexes -- the primary key on `name` covers all lookups.

## How Change-Point Detection Uses It

Detection config resolves through a 3-tier priority chain:

1. **Per-objective override** (`change_point_config` table) -- highest priority. Sparse:
   rows exist only when explicitly configured.
2. **Copy-forward** from previous SLO version (via the `SLOObjective` relationship).
3. **System defaults** from `configuration` table -- lowest priority. Loaded by
   `get_change_point_defaults()` at the start of each detection run.

Two algorithm-tuning keys (`pvalue_strict_threshold`, `pvalue_moderate_threshold`) always
come from system defaults, even when a per-objective override exists, because they control
the two-pass split/merge behavior rather than per-metric sensitivity.

**Configuration keys** (all prefixed `change_point.`):

| Key | Type | Controls |
|-----|------|---------|
| `enabled` | bool | Whether detection runs at all |
| `higher_is_better` | bool | Direction semantics (regression vs improvement) |
| `window_size` | int | Sliding window length for the split phase |
| `max_pvalue` | float | Significance threshold for the merge phase |
| `min_magnitude` | float | Minimum change magnitude to keep a CP |
| `min_sample_size` | int | Minimum history length before detection runs |
| `pvalue_strict_threshold` | float | Strict p-value cutoff (algorithm tuning, system-only) |
| `pvalue_moderate_threshold` | float | Moderate p-value cutoff (algorithm tuning, system-only) |

## Testing

Integration tests in `tests/configuration/db/test_repository.py` (132 lines) cover:

- `get_all()` with and without prefix filtering
- `get_by_name()` lookup
- `update_value()` with valid input
- Type validation rejection (invalid bool/int/float values)
- `get_change_point_defaults()` returning a correctly typed dict
- Bool validation edge cases

No HTTP-level router tests exist.
