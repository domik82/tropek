# SLO Templates & Groups — Phase 3 Backend Design

**Date:** 2026-03-24
**Status:** Approved (brainstorm)
**Parent spec:** `docs/superpowers/specs/2026-03-23-slo-linking-model-redesign.md` (Phase 3, steps 11-15)
**Depends on:** Phase 1-2 (merged to main — `kind`, `sli_name`, `sli_version`, `generated_by_group_id` on SLODefinition; `slo_bindings` table)

---

## Scope

Backend-only. Adds SLO template support, SLO group generator with regeneration engine, template bindings, and trigger integration. UI (Phase 4) is a separate plan.

---

## 1. Data Model

### `slo_groups` table (new)

```sql
CREATE TABLE slo_groups (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR NOT NULL,
  display_name VARCHAR,
  template_slo_name VARCHAR NOT NULL,
  template_slo_version INTEGER NOT NULL,
  gen_variables JSONB NOT NULL DEFAULT '{}',
  tags JSONB NOT NULL DEFAULT '{}',
  author VARCHAR,
  version INTEGER NOT NULL DEFAULT 1,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Partial unique: only one active group per name
CREATE UNIQUE INDEX uq_slo_groups_name_active ON slo_groups (name) WHERE active = true;
```

### `template_bindings` table (new)

```sql
CREATE TABLE template_bindings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  target_type VARCHAR NOT NULL CHECK (target_type IN ('asset', 'asset_group')),
  target_id UUID NOT NULL,
  template_group_name VARCHAR NOT NULL,
  data_source_name VARCHAR NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (target_type, target_id, template_group_name)
);
CREATE INDEX idx_template_bindings_target ON template_bindings (target_type, target_id);
```

### Modified: `slo_definitions`

Add FK constraint on `generated_by_group_id` → `slo_groups.id`. Column already exists (nullable UUID, added in Phase 1-2). Update the ORM model in `models.py` to add `ForeignKey("slo_groups.id")` on the `generated_by_group_id` column — Alembic autogenerate picks up FK from the ORM model, not just the migration.

---

## 2. Module Structure

New module at `api/app/modules/slo_groups/`:

```
api/app/modules/slo_groups/
├── __init__.py
├── generator.py        # Pure: template + gen_variables → SLO specs
├── regeneration.py     # Pure: old state + new template → regeneration plan
├── repository.py       # SLOGroupRepository + TemplateBindingRepository
├── schemas.py          # Pydantic request/response schemas
├── router.py           # FastAPI endpoints
```

---

## 3. Generator (`generator.py`) — Pure, No I/O

### Data Types

```python
@dataclass
class GeneratedSLOSpec:
    """One generated SLO ready to persist."""
    name: str
    sli_name: str
    sli_version: int
    variables: dict[str, Any]
    objectives: list[dict[str, Any]]
    total_score_pass_threshold: float
    total_score_warning_threshold: float
    comparison: dict[str, Any]
    tags: dict[str, Any]
```

### Function

```python
def generate_slo_specs(
    template: TemplateInput,
    gen_variables: dict[str, list[str]],
) -> list[GeneratedSLOSpec]:
```

`TemplateInput` is a protocol/dataclass with the fields needed from the template SLO (name, sli_name, sli_version, variables, objectives, scoring, comparison, tags). This avoids importing the ORM model.

### Logic

1. **Validate**: All `gen_variables` lists must be the same length. At least one key. No empty lists.
2. **For each row index** `i` in range(len(first_list)):
   - Build substitution map: `{key: gen_variables[key][i] for key in gen_variables}`
   - Substitute `$__gen_<key>` in template name → generated SLO name
   - Substitute `$__gen_<key>` in template variables values → generated variables
   - Copy objectives as-is (objectives reference SLI indicator names, not gen variables)
   - Add tags: `{"slo_group": group_name, "generated": "true"}` merged with template tags
3. Return list of `GeneratedSLOSpec`

### Validation Warnings

- If template has no `$__gen_` variables in name or variables dict, return a warning (not an error) — the caller decides whether to block or proceed. This matches the spec's "warn, not block" behavior.

---

## 4. Regeneration Engine (`regeneration.py`) — Pure, No I/O

### Input/Output

```python
@dataclass
class RegenerationPlan:
    """What to do when a group is updated."""
    to_create: list[GeneratedSLOSpec]                    # new rows in gen_variables
    to_update: list[UpdateAction]                          # what to regenerate

@dataclass
class UpdateAction:
    """One SLO to regenerate with a new version."""
    spec: GeneratedSLOSpec
    comparable_from_version: int | None  # None = preserve existing value
    to_deactivate: list[str]                              # SLO names to deactivate

def plan_regeneration(
    old_generated: list[OldSLOState],
    new_specs: list[GeneratedSLOSpec],
    old_sli_indicators: dict[str, Any],
    new_sli_indicators: dict[str, Any],
    template_variables_changed: bool,
) -> RegenerationPlan:
```

`OldSLOState` is a protocol/dataclass with: `name`, `comparable_from_version`.

### `comparable_from_version` Rules

From the parent spec section 3:

| Change | `comparable_from_version` | Rationale |
|---|---|---|
| Criteria changed (pass/warn thresholds, weights) | Preserve existing value | Same queries, only judgment changed |
| SLI version bump, queries unchanged | Preserve existing value | Queries produce identical values |
| SLI version bump, queries changed | Set to new generated version | Different queries, old baselines not comparable |
| Template variables changed (non-`$__gen_`) | Set to new generated version | Variable substitution changes query text |
| Values added | N/A (new SLO, version 1) | `comparable_from_version = 1` |
| Values removed | N/A (SLO deactivated) | History preserved |

### Query Change Detection

Strict textual comparison of `old_sli_indicators` vs `new_sli_indicators` — values are compared as `str(old) == str(new)`. If any key differs in value, or keys are added/removed → queries changed. Intentionally conservative.

### Matching Logic

Match old generated SLOs to new specs by **name** (the generated SLO name is deterministic from template name + gen_variables). Names present in new but not old → `to_create`. Names present in both → `to_update`. Names present in old but not new → `to_deactivate`.

---

## 5. Repository Layer

### `SLOGroupRepository`

```python
class SLOGroupRepository:
    async def create(self, *, name, display_name, template_slo_name,
                     template_slo_version, gen_variables, tags, author) -> SLOGroup
    async def get_by_name(self, name: str) -> SLOGroup | None       # active only
    async def get_by_id(self, id: uuid.UUID) -> SLOGroup | None
    async def list_all(self, *, tag_key=None, tag_val=None) -> list[SLOGroup]
    async def update(self, name: str, *, template_slo_name=None,     # bumps version + updated_at
                     template_slo_version=None, gen_variables=None,
                     display_name=None, tags=None) -> SLOGroup
    async def deactivate(self, name: str) -> None                    # sets active=false
    async def list_groups_by_template(self, template_slo_name: str) -> list[SLOGroup]
```

Thin CRUD — no business logic. The router orchestrates generator + repos.

### `TemplateBindingRepository`

```python
class TemplateBindingRepository:
    async def create(self, *, target_type, target_id,
                     template_group_name, data_source_name) -> TemplateBinding
    async def list_by_target(self, target_type, target_id) -> list[TemplateBinding]
    async def list_by_group_name(self, template_group_name) -> list[TemplateBinding]
    async def delete_by_target_and_group(self, target_type, target_id,
                                          template_group_name) -> None
    async def delete_all_by_group(self, template_group_name) -> None
```

---

## 6. Schemas

### Request

```python
class SLOGroupCreate(BaseModel):
    name: str
    display_name: str | None = None
    template_slo_name: str
    template_slo_version: int
    gen_variables: dict[str, list[str]]
    tags: dict[str, Any] = {}
    author: str | None = None

class SLOGroupUpdate(BaseModel):
    template_slo_name: str | None = None      # if provided, template_slo_version is required too
    template_slo_version: int | None = None   # if provided, template_slo_name is required too
    gen_variables: dict[str, list[str]] | None = None
    display_name: str | None = None
    tags: dict[str, Any] | None = None

class ExtractRequest(BaseModel):
    slo_name: str                    # which generated SLO to extract
    new_name: str                    # standalone name for the extracted SLO

class TemplateBindingCreate(BaseModel):
    template_group_name: str
    data_source_name: str
```

### Response

```python
class SLOGroupRead(BaseModel):
    id: uuid.UUID
    name: str
    display_name: str | None
    template_slo_name: str
    template_slo_version: int
    gen_variables: dict[str, list[str]]
    tags: dict[str, Any]
    author: str | None
    version: int
    active: bool
    created_at: datetime
    updated_at: datetime
    generated_slo_count: int         # computed via COUNT query in repository's get/list methods

class TemplateBindingRead(BaseModel):
    id: uuid.UUID
    target_type: str
    target_id: uuid.UUID
    template_group_name: str
    data_source_name: str
    created_at: datetime
```

---

## 7. API Endpoints

### SLO Group CRUD

| Endpoint | Method | Status | Purpose |
|---|---|---|---|
| `/slo-groups` | POST | 201 | Create group + generate SLOs (atomic) |
| `/slo-groups` | GET | 200 | List groups (tag filter) |
| `/slo-groups/{name}` | GET | 200 | Group detail + generated SLO names |
| `/slo-groups/{name}` | PUT | 200 | Update group → regeneration (atomic) |
| `/slo-groups/{name}` | DELETE | 204 | Deactivate group + generated SLOs + template bindings |
| `/slo-groups/{name}/extract` | POST | 201 | Extract generated SLO to standalone |

### Template Binding CRUD

| Endpoint | Method | Status | Purpose |
|---|---|---|---|
| `/assets/{name}/template-bindings` | GET | 200 | List template bindings for asset |
| `/assets/{name}/template-bindings` | POST | 201 | Create template binding (validates adapter_type) |
| `/assets/{name}/template-bindings/{group_name}` | DELETE | 204 | Delete template binding |
| `/asset-groups/{name}/template-bindings` | GET | 200 | List template bindings for group |
| `/asset-groups/{name}/template-bindings` | POST | 201 | Create template binding |
| `/asset-groups/{name}/template-bindings/{group_name}` | DELETE | 204 | Delete template binding |

### Create Flow (POST `/slo-groups`)

1. Validate template SLO exists, is `kind: "template"`, at the specified version
2. Run `generate_slo_specs()` — get list of specs + any warnings
3. Check for SLO name collisions (any generated name already exists as active standalone SLO → 409)
4. Create `SLOGroup` row
5. Create generated `SLODefinition` rows via `SLORepository.create()` with `kind="standard"`, `generated_by_group_id=group.id`. Note: `SLORepository.create()` must be extended to accept `generated_by_group_id` as a parameter (it currently doesn't).
6. Return group + warnings (if template had no `$__gen_` vars)
7. All in one transaction

### Update Flow (PUT `/slo-groups/{name}`)

1. Load existing group + old generated SLOs + old SLI indicators
2. If template changed: load new template, validate it's `kind: "template"`
3. Run `generate_slo_specs()` with new template + new gen_variables
4. Load new SLI indicators (if SLI version changed)
5. Run `plan_regeneration()` → get plan
6. Apply plan:
   - `to_create`: create new SLO versions
   - `to_update`: create new SLO versions with computed `comparable_from_version`
   - `to_deactivate`: set `active=false` on old SLOs
7. Update group row (bump version, updated_at)
8. All in one transaction

### Extract Flow (POST `/slo-groups/{name}/extract`)

1. Find the generated SLO by name, verify it belongs to this group (`generated_by_group_id` matches)
2. Create standalone copy: new name, `kind="standard"`, `generated_by_group_id=NULL`, `forked_from_group` tag
3. Find the row index: re-run `generate_slo_specs()` on the current group state to produce the name list, find the index where `name == slo_name`. Remove that index from all `gen_variables` lists.
4. For every `template_binding` referencing this group: create a corresponding `slo_binding` for the extracted SLO with same `target_type`, `target_id`, `data_source_name`
5. Bump group version
6. All in one transaction

### Adapter Type Validation (template bindings)

On create: resolve the group's template SLO → its `sli_name` → SLI definition → `adapter_type`. Datasource's `adapter_type` must match. Same pattern as `slo_bindings`.

---

## 8. Trigger Integration

Add a new function `resolve_all_bindings_for_asset()` in `trigger.py` that returns the full set of `(slo_name, data_source_name)` pairs for an asset. This is a **new function** — `resolve_single_trigger()` stays unchanged (it takes one SLO name and resolves it). The new function is called by the evaluation trigger endpoint to discover *which* SLOs to evaluate.

```python
async def resolve_all_bindings_for_asset(
    asset_id: uuid.UUID,
    group_ids: list[uuid.UUID],
    binding_repo: SLOBindingReader,
    template_binding_repo: TemplateBindingReader,
    slo_repo: SLOReader,
) -> list[ResolvedBinding]:
```

Steps:
1. Collect direct `slo_bindings` via `binding_repo.list_for_asset_evaluation(asset_id, group_ids)`
2. **NEW**: Query `template_binding_repo.list_for_asset_evaluation(asset_id, group_ids)` — returns template bindings for asset directly + via its groups
3. **NEW**: For each template binding, expand to generated SLOs: query `SLODefinition WHERE generated_by_group_id IN (group_ids from template bindings) AND active = true`
4. Each generated SLO becomes a `(slo_name, data_source_name)` pair using the template binding's datasource. Template-expanded SLOs have no `comparison_rules` (baselines use defaults).
5. Merge with direct bindings. Precedence: asset direct > group direct > asset template > group template
6. Deduplicate by SLO name — highest precedence wins

Add `list_for_asset_evaluation()` to `TemplateBindingRepository`:
```python
async def list_for_asset_evaluation(
    self, asset_id: uuid.UUID, group_ids: list[uuid.UUID]
) -> list[TemplateBinding]:
```

Same pattern as `SLOBindingRepository.list_for_asset_evaluation()`.

**Batch trigger (`trigger_service.py`)**: Deferred to Phase 5 — continues using current resolution path.

---

## 9. Testing Strategy

### Unit Tests (pure, no DB)

**`tests/engine/test_generator.py`**:
- Happy path: 3 variables, 3 rows → 3 specs with correct substitution
- Validates mismatched list lengths → error
- Validates empty lists → error
- Validates no keys → error
- Warning when template has no `$__gen_` variables
- Special characters in gen_variable values
- `$__gen_` substitution in name and variables, but NOT in objectives

**`tests/engine/test_regeneration.py`**:
- Criteria-only change → preserve `comparable_from_version`
- SLI version bump, same queries → preserve
- SLI version bump, different queries → set to new version
- Template variables changed → set to new version
- New rows added → `to_create` with `comparable_from_version=1`
- Rows removed → `to_deactivate`
- Mixed scenario: some added, some updated, some removed

### Integration Tests (DB)

**`tests/db/test_slo_groups.py`**:
- Create group → verify generated SLOs exist with correct fields
- Create group with name collision → 409
- Update group (add row) → new generated SLO appears
- Update group (remove row) → generated SLO deactivated
- Update group (change template version) → regeneration with correct `comparable_from_version`
- Extract generated SLO → standalone copy created, bindings duplicated, group row updated
- Deactivate group → generated SLOs deactivated, template bindings removed
- List groups with tag filter
- Template binding CRUD (create, list, delete)
- Template binding adapter_type validation
- Template binding duplicate rejection

### Trigger Tests

**`tests/engine/test_trigger.py`** (extend existing):
- Asset with both direct binding and template binding → both resolved
- Template binding precedence: direct binding wins over template for same SLO name

---

## 10. Seed Data

To exercise the feature end-to-end after Phase 3:

**New SLI** (`bootstrap_mock/manifests/sli-definitions.yaml`):
- `plugin-metrics-sli`: adapter_type `prometheus`, indicators: `cpu_usage` (query with `$process_name`), `memory_usage` (query with `$process_name`)

**New template SLO** (`bootstrap_mock/manifests/slo-definitions.yaml`):
- `plugin-health-tpl`: kind `template`, sli_name `plugin-metrics-sli`, sli_version 1, name pattern `plugin/$__gen_process_name`, variables `{"process_name": "$__gen_process_name", "AGGREGATION_WINDOW": "5m"}`

**New SLO group** (new manifest file `bootstrap_mock/manifests/slo-groups.yaml`):
- `app-x-plugins`: template `plugin-health-tpl` v1, gen_variables `{"process_name": ["auth", "cache", "db"]}`

**New template binding** (new manifest file `bootstrap_mock/manifests/template-bindings.yaml`):
- Bind `app-x-plugins` to asset group `core-services` with datasource `prometheus-local`

**Client library updates** (`clients/python/tropek_client/`):
- Add `SLOGroup` and `TemplateBinding` manifest kinds
- Add client methods for group CRUD and template binding CRUD

**Seed evaluations** (`scripts/seed_evaluations.py`):
- Add triggers for the 3 generated SLOs against assets in `core-services`

---

## 11. Migration

Single Alembic migration (autogenerated via `./scripts/db-regen-migrations.sh`):
- Creates `slo_groups` table with partial unique index
- Creates `template_bindings` table with unique constraint and index
- Adds FK constraint on `slo_definitions.generated_by_group_id` → `slo_groups.id`
