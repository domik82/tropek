# API Schema Consistency & Client DX Improvements

## Goal

Fix CRUD inconsistencies across API schemas (missing fields in Update/Create) and add client-side convenience methods for versioned resources and simplified configuration updates.

## Context

An automated audit (`scripts/audit_api_schemas.py`) comparing Create/Read/Update schema triplets found 15 findings. After triage, 5 are confirmed bugs (missing fields), the rest are intentional design patterns (versioned resources, nested member management, migration-seeded config).

## Triage Summary

### Intentional — no fix needed

| Resource | Finding | Reason |
|---|---|---|
| AssetGroup | `name`, `members`, `subgroups` set-once | `name` is immutable identifier; members/subgroups managed via dedicated POST/DELETE endpoints |
| Configuration | Only `value` in Update | Entries are migration-seeded knobs; `name`, `description`, `value_type` are schema, not user data |
| SLIDefinition | `active` read-only | Versioned resource — new versions via POST, deactivation via DELETE |
| SLODefinition | `active`, `sli_definition_id` read-only | Same versioned pattern |
| Annotation | `slo_evaluation_id`, `note_group_id`, etc. read-only | Set by URL path context (standard REST nesting) |
| SLOGroupAssignment | Only `data_source_name` in Upsert | Identity is in URL; datasource is the only settable field |

### Bugs — fixing in this scope

| Resource | Finding | Fix |
|---|---|---|
| DataSourceUpdate | Missing `name`, `adapter_type` | Add as optional fields |
| AssetCreate | Missing `heatmap_config` | Add as optional field |
| SLOGroupUpdate | Missing `author` | Add as optional field |
| AssetTypeUpdate | Missing `is_default` | Add as optional field |

## Design

### 1. API Schema Fixes

Each fix adds the missing field(s) as optional to the relevant Pydantic schema in `api/tropek/modules/*/schemas.py`. The repository update methods need to handle the new fields (pass them through to the ORM model update).

**DataSourceUpdate** (`api/tropek/modules/datasource/schemas.py`):
- Add `name: SafeStr | None = None`
- Add `adapter_type: SafeStr | None = None`
- Repository: handle rename (uniqueness check) and adapter_type update

**AssetCreate** (`api/tropek/modules/assets/schemas.py`):
- Add `heatmap_config: dict[str, Any] | None = None`
- Repository: pass through to model on creation

**SLOGroupUpdate** (`api/tropek/modules/slo_groups/schemas.py`):
- Add `author: SafeStr | None = None`

**AssetTypeUpdate** (`api/tropek/modules/assets/schemas.py`):
- Add `is_default: bool | None = None`
- Repository: if `is_default=True`, clear the flag on the current default first (same logic as the `set-default` endpoint)

After all schema changes, regenerate `api/openapi.json`.

### 2. Client Model Updates

Mirror each API fix in the client Pydantic models under `clients/python/tropek_client/models/`:

- `DataSourceUpdate`: add `name: str | None = None`, `adapter_type: str | None = None`
- `AssetCreate`: add `heatmap_config: dict[str, Any] | None = None`
- `SLOGroupUpdate`: add `author: str | None = None`
- `AssetTypeUpdate`: add `is_default: bool | None = None`

Drift tests should pass after alignment.

### 3. Client DX Improvements

**Simplified Configuration.update**: Change the client method signature from `update(name, body: ConfigurationUpdate)` to `update(name: str, value: str)`. The method builds `{"value": value}` internally. `ConfigurationUpdate` stays in the models package for drift test coverage but is no longer part of the user-facing client API.

**SLI new_version helper**: `client.slis.new_version(name, **overrides)` fetches the current active version, copies all Create-compatible fields into an `SLIDefinitionCreate`, applies overrides via `model_copy(update=overrides)`, and calls `create()`. Server-managed fields (`id`, `version`, `active`, `created_at`) are not copied.

**SLO new_version helper**: Same pattern as SLI. Additional complexity: `SLODefinitionRead.objectives` contains `SLOObjectiveRead` (has `sort_order`) but `SLODefinitionCreate` expects dicts/`SLOObjectiveIn` (no `sort_order`). The helper strips `sort_order` when copying objectives. Same for `comparison` (Read vs Config nested types) — dump to dict and reconstruct.

### 4. Documentation

Add a note to the client README that asset names are globally unique across the system. There is no per-group scoping (e.g., two groups cannot each have an asset named `load_test`). This is a known limitation.

### 5. Testing

**API integration tests**: For each schema fix, verify the new fields work end-to-end:
- Rename a DataSource via PATCH with `name`; change `adapter_type`
- Create an Asset with `heatmap_config` populated
- Update an SLOGroup's `author`
- Update an AssetType's `is_default` via PATCH

**Client unit tests** (respx mocks):
- `test_configuration_update_simple_args`: verify `update(name, value)` sends `{"value": "..."}` body
- `test_sli_new_version`: mock GET returning current SLI, verify POST sends merged body with overrides applied
- `test_slo_new_version`: same pattern, verify `sort_order` stripped from objectives

**Drift tests**: Should pass after client models aligned with regenerated openapi.json.

**Audit re-run**: `scripts/audit_api_schemas.py` re-run at end to confirm the 4 bug findings are resolved.

## Out of Scope

- Asset identity model changes (per-group scoping) — known limitation, documented
- Configuration Create endpoint — entries are migration-seeded, not user-created
- SLI/SLO Update endpoints — versioning-via-POST is the intended pattern; `new_version` helper provides the UX improvement client-side
