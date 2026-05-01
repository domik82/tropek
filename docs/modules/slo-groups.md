# SLO Groups

## Purpose

SLO groups provide template-based SLO generation: define one template SLO, supply a table of
variable values, and get N fully-formed SLO definitions -- one per row. This removes the manual
duplication of maintaining near-identical SLOs for many assets (services, environments, regions).

A group owns its generated SLOs. Updating the group triggers automatic regeneration; deleting the
group deactivates all of its generated SLOs. Individual generated SLOs can also be extracted to
standalone definitions when they need to diverge from the group.

## Key Concepts

| Concept | What It Is |
|---------|------------|
| **Template SLO** | An SLO definition with `kind: template`. Serves as the blueprint. Contains `$__gen_<key>` placeholders in its name and variable values. |
| **`$__gen_<key>` placeholders** | Substitution tokens matched by regex `\$__gen_(\w+)`. Replaced per-row from `gen_variables` in the template's name and `variables` block. |
| **`gen_variables`** | Column-oriented table supplied at group creation. Each key is a column name (must match a `$__gen_<key>` placeholder); each value is a list of strings. All lists must be the same length. Row `i` produces one generated SLO. |
| **Generated SLO** | A standard SLO definition created from the template with substitutions applied. Carries tags `slo_group: <group_name>` and `generated: true`. Managed exclusively through the group. |
| **Template binding** | The group stores an FK to the exact template SLO version used at creation. Updating the group can re-point to a newer template version. |
| **Regeneration** | When a group is updated, a diff engine computes which SLOs to create, re-version, or deactivate. |
| **Extraction** | Removes a generated SLO from group ownership and creates an independent standalone copy. |

## Code Generation Engine

The generation logic lives in two pure-function modules with no I/O, making them fully
unit-testable:

### `generate_slo_specs()` (generator.py)

Takes a `TemplateInput` protocol object, a `gen_variables` dict, and a group name.
For each row in the variable table:

1. Builds a substitution map `{key: values[i]}` from the column-oriented table.
2. Replaces all `$__gen_<key>` placeholders in the template name and variable values.
3. Copies objectives unchanged (no substitution in objective criteria or SLI references).
4. Merges tags with `slo_group: <group_name>` and `generated: true` markers.

Returns a `GeneratorResult` containing the list of `GeneratedSLOSpec` objects plus any
warnings (e.g., if the template has no `$__gen_` placeholders, all generated SLOs would
be identical copies).

Validation (`validate_gen_variables()`): rejects empty tables, empty column lists, and
mismatched list lengths.

### `plan_regeneration()` (regeneration.py)

Computes a `RegenerationPlan` with three lists:

- **`to_create`**: new SLO names not in the old set.
- **`to_update`**: existing names to re-version (new SLO version created).
- **`to_deactivate`**: old SLO names no longer in the new set.

**Baseline break detection**: `comparable_from_version` is reset (set to `None`, meaning
"start fresh") only when:

- Existing SLI indicator queries were modified or removed (adding new indicators is OK).
- Template variables changed.

Otherwise, the existing `comparable_from_version` is preserved, maintaining baseline
continuity across criteria-only changes.

The `_indicators_changed()` helper checks whether existing keys in the SLI indicator map
were modified or removed. Adding new keys is explicitly not a breaking change.

## Display Groups

Display groups are a separate, simpler concept for organizing SLOs in the UI. They
reference SLO **concept names** (strings), not specific SLO definition IDs or versions.
They are purely an organizational concern with no impact on evaluation logic.

### Display Group Features

- Flat or hierarchical via `parent_id`.
- Ordered by `sort_order`, then name.
- Members are added/removed by SLO concept name (idempotent add).
- Hard-deleted (no soft delete, no versioning, no tags, no cache).

### Display Group Endpoints

| Method | Path | What It Does |
|--------|------|--------------|
| `POST` | `/display-groups` | Create a display group. |
| `GET` | `/display-groups` | List all display groups (ordered by sort_order, name). |
| `DELETE` | `/display-groups/{name}` | Delete a display group (cascades to members). |
| `GET` | `/display-groups/{group_id}/members` | List SLO names in a group. |
| `POST` | `/display-groups/{group_id}/members` | Add an SLO name to a group (idempotent). |
| `DELETE` | `/display-groups/{group_id}/members/{slo_name}` | Remove an SLO name from a group. |

## gen_variables Structure

`gen_variables` is a column-oriented table. Example with two columns and three rows --
produces three generated SLOs:

```json
{
  "service": ["auth", "cache", "db"],
  "env":     ["prod", "prod",  "prod"]
}
```

Row 0 substitutes `$__gen_service` -> `auth`, `$__gen_env` -> `prod`. Row 1 substitutes
`cache` / `prod`, and so on. Substitution applies to the template SLO's **name** and all
string values in the template's **`variables` block**. Objective criteria, thresholds, and
comparison config are copied verbatim -- placeholders are not expanded there.

## Typical Workflows

### Create a group

1. Create a template SLO via `POST /slo-definitions` with `kind: template`. Use
   `$__gen_<key>` placeholders in the SLO name and any variable values that should vary.
2. Create the group: `POST /slo-groups` with the template name, target version, and
   `gen_variables`. The API immediately generates all SLO definitions and returns the group.

### Multi-environment usage

Use the same template for TEST and PROD by creating two groups with different `gen_variables`:

- Group `perf-test-slos` -> `gen_variables: { env: ["test"], service: ["auth"] }`
- Group `perf-prod-slos` -> `gen_variables: { env: ["prod"], service: ["auth"] }`

Both groups reference the same template SLO. Criteria changes in the template propagate
to both groups when you update them to point at the new template version.

### Update a group (regeneration)

`PUT /slo-groups/{name}` -- supply any combination of: new `template_slo_name`/`template_slo_version`,
updated `gen_variables`, or metadata (`display_name`, `tags`). The regeneration engine diffs
old vs new:

- Rows with new names are **created**.
- Rows whose names exist in both old and new are **re-versioned**.
- Rows whose names no longer appear are **deactivated**.

### Extract a generated SLO

When one generated SLO needs to deviate from the template (custom criteria, different
comparison window), extract it:

`POST /slo-groups/{name}/extract` with body `{ "slo_name": "<generated-name>", "new_name": "<standalone-name>" }`

The operation:

1. Creates a standalone copy of the generated SLO under `new_name` (strips the `slo_group` tag).
2. Deactivates the original generated SLO.
3. Removes the corresponding row from the group's `gen_variables` (via `_shrink_gen_variables()`).
4. If the group has no remaining rows, the group itself is deactivated.

## SLO Group Endpoints

| Method | Path | What It Does |
|--------|------|--------------|
| `POST` | `/slo-groups` | Create a group and generate SLO definitions from the template. |
| `GET` | `/slo-groups` | List all active groups. Supports `tag_key`, `tag_val` filters. |
| `GET` | `/slo-groups/{name}` | Get a group by name, including generated SLO count. |
| `PUT` | `/slo-groups/{name}` | Update a group and trigger regeneration of generated SLOs. |
| `DELETE` | `/slo-groups/{name}` | Deactivate the group and all its generated SLOs. |
| `POST` | `/slo-groups/{name}/extract` | Extract a generated SLO to a standalone definition. |

## SLO Group Versioning

SLO groups use a hybrid versioning approach, different from the
[SLO/SLI versioning model](registries.md#versioning-model):

- The group has a `version` field that is manually bumped (`group.version += 1`) on each update.
- Groups use soft-delete (`active = false`), like SLO/SLI definitions.
- But groups are not name-versioned in the SLO/SLI sense -- there is no `DISTINCT ON (name)`
  pattern. Each group name maps to exactly one row.
- SLO groups do not use `TagQueryMixin` despite having a `tags` column. Tag filtering is
  implemented inline in the repository's `list_all()` method.
- SLO groups do not use Redis caching.

## Source Code Layout

```
api/tropek/modules/slo_groups/
    generator.py      # generate_slo_specs() — pure template expansion
    regeneration.py   # plan_regeneration() — pure diff computation
    repository.py     # SLOGroupRepository (CRUD, version bumping, soft-delete)
    router.py         # Endpoints + orchestration helpers
    schemas.py        # SLOGroupCreate/Update/Read, ExtractRequest

api/tropek/modules/display_groups/
    repository.py     # DisplayGroupRepository (simple CRUD, member management)
    router.py         # Endpoints for display groups and members
    schemas.py        # DisplayGroupCreate/Read, DisplayGroupMemberAdd
```

## Gotchas / Design Decisions

- **Generated SLOs are read-only via `/slo-definitions`.** They are managed only through
  the group. Attempting to update a generated SLO directly (by POSTing to `/slo-definitions`
  with the same name) will succeed but the new version will not be linked to the group --
  the next group regeneration will overwrite it. Extract first if you need independent control.
- **Template version is pinned at creation.** The group stores an FK to the exact template
  SLO definition version used. Updating the template SLO does not automatically re-generate
  the group -- you must PUT the group and specify the new `template_slo_version`.
- **`$__gen_` substitution applies only to name and variable values.** Objective SLIs,
  criteria strings, thresholds, and the comparison block are cloned verbatim. If your
  criteria need to vary per row, extraction followed by manual editing is the escape hatch.
- **All `gen_variables` lists must have equal length.** A validation error is returned if
  they do not. An empty list in any column is also rejected.
- **Name collisions are detected eagerly.** During group creation, if any generated SLO
  name would collide with an existing active SLO, the whole request is rejected.
- **The template SLO itself is never modified by group operations.** Groups read the
  template; they never write back to it.
- **Significant orchestration logic lives in router helpers** (`_build_group_read`,
  `_load_template_slo`, `_apply_regeneration_plan`, `_shrink_gen_variables`, etc.) rather
  than in a dedicated service class. This is the most complex router in the codebase.
- **Display groups are fully decoupled from SLO groups.** Despite similar names, display
  groups are a UI organizational concept. They reference SLO names as strings and have no
  effect on evaluation logic, no versioning, no tags, and no caching.
