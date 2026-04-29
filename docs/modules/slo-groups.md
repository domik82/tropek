# SLO Groups

## Purpose

SLO groups provide template-based SLO generation: define one template SLO, supply a table of
variable values, and get N fully-formed SLO definitions — one per row. This removes the manual
duplication of maintaining near-identical SLOs for many assets (services, environments, regions).

A group owns its generated SLOs. Updating the group triggers automatic regeneration; deleting the
group deactivates all of its generated SLOs. Individual generated SLOs can also be extracted to
standalone definitions when they need to diverge from the group.

## Key Concepts

| Concept | What It Is |
|---------|------------|
| **Template SLO** | An SLO definition with `kind: template`. Serves as the blueprint. Contains `$__gen_<key>` placeholders in its name and variable values. |
| **`$__gen_<key>` placeholders** | Substitution tokens in the template's name and `variables` block. Replaced per-row from `gen_variables`. |
| **`gen_variables`** | Column-oriented table supplied at group creation. Each key is a column name (must match a `$__gen_<key>` placeholder); each value is a list of strings. All lists must be the same length. Row `i` produces one generated SLO. |
| **Generated SLO** | A standard SLO definition created from the template with substitutions applied. Carries tags `slo_group: <group_name>` and `generated: true`. Read-only via normal SLO endpoints — managed exclusively through the group. |
| **Template binding** | The group stores an FK to the exact template SLO version used at creation. Updating the group can re-point to a newer template version. |
| **Regeneration** | When a group is updated (new template version, changed `gen_variables`), the group computes a diff: new rows are created, changed rows are re-versioned, removed rows are deactivated. |
| **Comparable-from-version** | Tracks from which SLO version baseline comparisons are valid. Preserved across criteria-only changes; reset when SLI queries or `gen_variables` change. |
| **Extraction** | Removes a generated SLO from group ownership and creates an independent copy under a new name. The original generated SLO is deactivated; the group's `gen_variables` row is removed. |

## gen_variables Structure

`gen_variables` is a column-oriented table. Example with two columns and three rows — produces
three generated SLOs:

```json
{
  "service": ["auth", "cache", "db"],
  "env":     ["prod", "prod",  "prod"]
}
```

Row 0 substitutes `$__gen_service` → `auth`, `$__gen_env` → `prod`. Row 1 substitutes `cache` /
`prod`, and so on. Substitution applies to the template SLO's **name** and all string values in
the template's **`variables` block**. Objective criteria, thresholds, and comparison config are
copied verbatim — placeholders are not expanded there.

## Typical Workflows

### Create a group (basic)

1. Create a template SLO via `POST /slo-definitions` with `kind: template`. Use
   `$__gen_<key>` placeholders in the SLO name and any variable values that should vary.
2. Create the group: `POST /slo-groups` with the template name, target version, and
   `gen_variables`. The API immediately generates all SLO definitions and returns the group.

### Multi-environment usage

Use the same template for TEST and PROD by creating two groups, each with different `gen_variables`:

- Group `perf-test-slos` → `gen_variables: { env: ["test"], service: ["auth"] }`
- Group `perf-prod-slos` → `gen_variables: { env: ["prod"], service: ["auth"] }`

Both groups reference the same template SLO. Criteria changes in the template propagate to both
groups when you update them to point at the new template version.

### Update a group (regeneration)

```
PUT /slo-groups/{name}
```

Supply any combination of: new `template_slo_name`/`template_slo_version`, updated
`gen_variables`, or metadata (`display_name`, `tags`). The regeneration engine diffs old vs new:

- Rows with new names are **created**.
- Rows whose names exist in both old and new are **re-versioned** (new SLO version created).
- Rows whose names no longer appear are **deactivated**.

Comparable-from-version is reset only when SLI query strings change or `gen_variables` are
modified — criteria-only template updates preserve baseline continuity.

### Extract a generated SLO

When one generated SLO needs to deviate from the group template (custom criteria, different
comparison window), extract it:

```
POST /slo-groups/{name}/extract
```

Body: `{ "slo_name": "<current-generated-name>", "new_name": "<standalone-name>" }`.

The operation:
1. Creates a standalone copy of the generated SLO under `new_name` (without the `slo_group` tag).
2. Deactivates the original generated SLO.
3. Removes the corresponding row from the group's `gen_variables`.
4. If the group has no remaining rows, the group itself is deactivated.

## Endpoints

| Method | Path | What It Does |
|--------|------|--------------|
| `POST` | `/slo-groups` | Create a group and generate SLO definitions from the template. |
| `GET` | `/slo-groups` | List all active groups. Supports `tag_key`, `tag_val` filters. |
| `GET` | `/slo-groups/{name}` | Get a group by name, including generated SLO count. |
| `PUT` | `/slo-groups/{name}` | Update a group and trigger regeneration of generated SLOs. |
| `DELETE` | `/slo-groups/{name}` | Deactivate the group and all its generated SLOs. |
| `POST` | `/slo-groups/{name}/extract` | Extract a generated SLO to a standalone definition and remove its row from the group. |

## Gotchas / Design Decisions

- **Generated SLOs are read-only via `/slo-definitions`.** They are managed only through the
  group. Attempting to update a generated SLO directly (by POSTing to `/slo-definitions` with
  the same name) will succeed but the new version will not be `generated_by_group_id`-linked —
  the next group regeneration will overwrite it. Extract first if you need independent control.
- **Template version is pinned at creation.** The group stores an FK to the exact template SLO
  definition version used. Updating the template SLO does not automatically re-generate the
  group — you must PUT the group and specify the new `template_slo_version`.
- **`$__gen_` substitution applies only to name and variable values.** Objective SLIs, criteria
  strings, thresholds, and the comparison block are cloned verbatim. If your criteria need to
  vary per row, extraction followed by manual editing is the escape hatch.
- **All `gen_variables` lists must have equal length.** A validation error is returned if they
  do not. An empty list in any column is also rejected.
- **Extraction shrinks `gen_variables` in place.** The group's `gen_variables` column loses the
  extracted row. If the last row is extracted, the group is deactivated.
- **DELETE cascades to generated SLOs.** Deactivating a group deactivates all its generated SLOs
  (soft delete — data is preserved). Evaluations that ran against those SLOs remain queryable.
- **The template SLO itself is never modified by group operations.** Groups read the template;
  they never write back to it.
- **Name collisions are detected eagerly.** During group creation, if any generated SLO name
  would collide with an existing active SLO, the whole request is rejected with a conflict error.
