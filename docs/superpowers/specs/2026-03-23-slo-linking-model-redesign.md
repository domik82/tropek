# SLO Linking Model Redesign & SLO Group Generator

**Date:** 2026-03-23
**Status:** Draft
**Supersedes:** Linking portions of `2026-03-23-adapter-protocol-and-slo-groups.md`

---

## Problem

The current linking model stores `(slo_name, sli_name, data_source_name)` per group/asset, treating SLO→SLI as a flexible binding. In practice this flexibility is unused and creates confusion:

- The SLO wizard collects datasource + SLI info but only creates the SLO definition — the user expects the SLO to be connected but it isn't.
- SLO objectives reference SLI indicator names as loose strings, making the coupling implicit but fragile.
- The 3-way link creates a combinatorial UI problem: pick SLO, pick SLI, pick datasource — when in reality SLO→SLI is always 1:1.
- The SLO Group Generator (templated bulk SLO creation) needs a clean model to build on.

## Design Principles

1. **SLO→SLI is explicit and pinned.** An SLO definition declares which SLI definition (and version) it uses. No separate binding needed.
2. **Datasource is a deployment concern.** The same SLO+SLI can run against different datasource instances (prod vs staging). Datasource is chosen when attaching to an asset, not when defining the SLO.
3. **SLI connects to adapter type, not instance.** An SLI definition declares `adapter_type: "prometheus"`, not a specific datasource. Any datasource of that type can execute its queries.
4. **SLO Groups are attached as a unit.** You don't link 30 individual SLOs — you attach one group, pick a datasource, done.

---

## 1. Entity Model

### SLI Definition (unchanged)

```
SLIDefinition
  name: str
  version: int (auto-increment per name)
  adapter_type: str                    # "prometheus", "datadog", etc.
  indicators: {name: query_template}   # e.g. {"cpu_usage": "rate(cpu{plugin='$process_name'}[$AGGREGATION_WINDOW])"}
  display_name, notes, author, tags
  active: bool
```

No changes. SLI already connects to adapter type, not instance.

### SLO Definition (modified)

```
SLODefinition
  name: str
  version: int (auto-increment per name)
  kind: "standard" | "template"        # NEW — default "standard"
  sli_name: str                        # NEW — explicit SLI reference
  sli_version: int                     # NEW — pinned version
  objectives: [{sli: "cpu_usage", pass_threshold: [...], ...}]
  total_score_pass_pct, total_score_warning_pct
  comparison: {...}
  variables: {key: value}
  display_name, notes, author, tags
  comparable_from_version: int
  active: bool
```

**New fields:**
- `sli_name` — which SLI definition this SLO uses. Objectives reference indicator names from this SLI.
- `sli_version` — pinned SLI version. When the SLI gets a new version, creating a new SLO version is required to adopt it. The `comparable_from_version` mechanism governs whether baselines remain valid across the version bump.
- `kind` — `"standard"` for normal SLOs, `"template"` for generator templates. Templates are excluded from direct evaluation (worker filters `kind = "standard"`).

**Validation (at creation time, applies to both standard and template):**
- Every objective's `sli` field must exist as a key in the referenced SLI definition's `indicators` dict at the pinned `sli_version`.
- `sli_version` must reference an existing version of the named SLI.

### SLO Template (kind = "template")

A template is a regular `SLODefinition` with `kind = "template"` and `$__gen_*` placeholders:

```
SLODefinition (kind: "template")
  name: "app_x/$__gen_process_name"
  sli_name: "plugin-metrics-sli"
  sli_version: 3
  variables: {
    "process_name": "$__gen_process_name",
    "host": "$__gen_host",
    "AGGREGATION_WINDOW": "5m"
  }
  objectives: [
    {sli: "cpu_usage", pass_threshold: ["<80"], weight: 1, key_sli: true},
    {sli: "memory_usage", pass_threshold: ["<1073741824"], weight: 1}
  ]
```

- `$__gen_<name>` prefix distinguishes generator-time placeholders from runtime variables (`$VARIABLE`). The `<name>` part matches the output variable name (what the SLI expects).
- Templates are versioned like any SLO.
- Validation: warn (not block) if a template has no `$__gen_` variables — it would generate identical copies (see `warn.png` mockup).

### SLO Group (new entity)

```
SLOGroup
  id: UUID
  name: str                           # "app_x_plugins"
  display_name: str
  template_slo_name: str              # references the template SLO
  template_slo_version: int           # pinned template version
  gen_variables: JSONB                # {"process_name": ["auth", "cache", "db"], "host": ["vm-1", "vm-2", "vm-3"]}
  tags: JSONB
  author: str
  version: int                        # auto-incremented on regeneration
  active: bool
  created_at: datetime
  updated_at: datetime
```

**Key points:**
- No `sli_name` — inherited from the template SLO's `sli_name`.
- No `data_source_name` — chosen at attachment time.
- `gen_variables` keys are **output variable names** (matching what the SLI expects, e.g. `process_name`). The template text uses `$__gen_<key>` as the placeholder (e.g. `$__gen_process_name`). The `__gen_` prefix distinguishes generator-time substitution from runtime variables like `$AGGREGATION_WINDOW`.
- **Row-aligned expansion:** All `gen_variables` lists must be the **same length**. Each row index produces one generated SLO. This is row-by-row, **not** cartesian product. Example:
  ```
  gen_variables: {
    "process_name": ["auth",  "cache", "db"],
    "host":         ["vm-1",  "vm-2",  "vm-3"]
  }
  → 3 SLOs: (auth, vm-1), (cache, vm-2), (db, vm-3)
  ```
  If a variable doesn't apply for a row, the user must provide an explicit empty string (`""`). The UI renders this as an editable table (columns = variable names, rows = generated SLOs).
- **Validation:** All lists must have equal length. At least one key required. Empty lists not allowed.
- The group generates read-only SLO instances. These are `SLODefinition` rows with `kind = "standard"` and a `generated_by_group_id` FK pointing back to the group. They are not independently editable.
- **Namespace isolation:** SLO group names and SLO definition names occupy separate namespaces (separate tables). No collision constraints needed between them. The UI sidebar shows them in distinct sections.

### Generated SLO Instances

When a group is created or regenerated, for each row in `gen_variables`:

```
Input:
  template name: "app_x/$__gen_process_name"
  template variables: {"process_name": "$__gen_process_name", "host": "$__gen_host", "AGGREGATION_WINDOW": "5m"}
  gen_variables row 0: {"process_name": "auth", "host": "vm-1"}

Output (SLODefinition, kind: "standard"):
  name: "app_x/auth"
  sli_name: "plugin-metrics-sli"     # inherited from template
  sli_version: 3                      # inherited from template
  variables: {"process_name": "auth", "host": "vm-1", "AGGREGATION_WINDOW": "5m"}
  tags: {"slo_group": "app_x_plugins", "generated": "true"}
  objectives: [same as template]
```

Generated SLOs are real `SLODefinition` rows — the evaluation engine doesn't know or care they came from a group.

**Version numbering:** Generated SLOs use the same auto-increment versioning as any SLO. First creation = version 1. Regeneration (template change) creates version 2, etc. The generated SLO's version is independent of the group's version. Name collisions with deactivated manually-created SLOs are prevented by the unique constraint on `(name, active=true)`; if a collision occurs, the group creation fails with a clear error naming the conflicting SLO.

**Discovery:** Generated SLOs belonging to a group are found via FK: `slo_definitions.generated_by_group_id = slo_groups.id AND active = true`. This provides referential integrity — deleting a group cascades correctly. Tags (`slo_group`, `generated`) are added for UI display but are not the source of truth for membership.

### Extraction (Customizing One Instance)

When a generated SLO needs custom criteria:
1. Copy into a new standalone SLO (new name, e.g. `app_x/abc_custom`, `kind: "standard"`, `generated_by_group_id = NULL`)
2. Add `forked_from_group: "app_x_plugins"` tag for traceability
3. Remove the row (same index across all `gen_variables` lists) from the group + bump group version (atomic transaction)
4. **Create replacement bindings:** For every `template_bindings` row that references this group, create a corresponding `slo_bindings` row for the extracted SLO with the same `target_type`, `target_id`, and `data_source_name`. This works for both asset-level and asset-group-level template bindings — the extracted SLO inherits the same binding shape. No need to enumerate individual assets.
5. The extracted SLO is fully independent — group regeneration doesn't touch it

### DataSource (unchanged)

```
DataSource
  name: str                           # "prometheus-prod"
  adapter_type: str                   # "prometheus"
  adapter_url: str
  display_name, tags
```

### Bindings (simplified)

The link model changes from a 3-way binding to a 2-way binding, and from four tables to two polymorphic tables.

**Current (4 tables, 3-way binding):**
```
asset_slo_links / asset_group_slo_links
  slo_name: str
  sli_name: str              ← REMOVED
  data_source_name: str
  comparison_rules: JSONB    ← PRESERVED on asset-level only
```

**New: `slo_bindings` table** — binds a standalone SLO to an asset or asset group:
```
slo_bindings
  id: UUID
  target_type: "asset" | "asset_group"
  target_id: UUID                      # references assets.id or asset_groups.id
  slo_name: str                        # SLI resolved from SLO definition
  data_source_name: str                # must match SLO's SLI adapter_type
  comparison_rules: JSONB              # per-asset baseline rules (null for asset_group targets)
  created_at: datetime
  UNIQUE (target_type, target_id, slo_name)
```

**New: `template_bindings` table** — binds a template group (all its generated SLOs) to an asset or asset group:
```
template_bindings
  id: UUID
  target_type: "asset" | "asset_group"
  target_id: UUID                      # references assets.id or asset_groups.id
  template_group_name: str             # attaches all generated SLOs at once
  data_source_name: str                # must match template's SLI adapter_type
  created_at: datetime
  UNIQUE (target_type, target_id, template_group_name)
```

**`link_name` removal:** The current `link_name` column (auto-generated as `{slo_name}--{sli_name}`) is replaced by the unique constraint on `(target_type, target_id, slo_name)`. No more `link_name`.

**Validation:** `data_source_name`'s `adapter_type` must match the SLO's (or template's) SLI definition's `adapter_type`. The UI filters the datasource dropdown to only show matching instances.

**Binding modification:** Bindings are immutable once created. To change a datasource, delete the binding and create a new one. This avoids partial-update semantics and keeps the audit trail clean.

**Datasource deletion:** When a datasource is deleted/deactivated, the API checks for referencing `slo_bindings` and `template_bindings`. If any exist, the deletion is blocked with an error listing the affected bindings. The user must reassign or remove bindings first. This is the same pattern used for SLI/SLO deletion today.

---

## 2. Evaluation Flow

### Triggering an Evaluation

When "evaluate asset X" is triggered:

1. **Resolve asset's groups:** Look up which asset groups asset X belongs to (via `asset_group_members`).
2. **Collect direct SLO bindings:** `slo_bindings WHERE (target_type='asset', target_id=X) OR (target_type='asset_group', target_id IN <groups>)` → list of `(slo_name, data_source_name, comparison_rules)`. For asset-group-level bindings, `comparison_rules` is NULL (group-level bindings don't carry per-asset overrides).
3. **Collect template bindings:** `template_bindings WHERE (target_type='asset', target_id=X) OR (target_type='asset_group', target_id IN <groups>)` → list of `(template_group_name, data_source_name)`.
4. **Expand template bindings:** For each, query generated SLOs via FK: `slo_definitions WHERE generated_by_group_id = <group_id> AND active = true`. Each produces `(slo_name, data_source_name)` pairs using the template binding's datasource.
5. **Merge:** Union of direct + expanded bindings. Precedence: asset-level direct > asset-group-level direct > asset-level template > asset-group-level template. If same SLO appears at multiple levels, the highest-precedence binding wins (allows overriding a group member's datasource or comparison_rules per-asset).
6. **Deduplicate across template groups:** If two different template groups both produce an SLO with the same name (unlikely given naming conventions, but possible), this is a configuration error. The evaluation logs a warning and uses the first match. The UI should prevent this at binding-creation time by checking for overlap.
7. **Resolve each:** SLO → pinned SLI version → indicators → variable substitution → queries to datasource

### Resolution Chain

```
Asset "vm-1-branch-X"
  └─ template_bindings(group: "app_x_plugins", ds: "prometheus-prod")
       └─ expand → 30 SLOs, each with sli_name + sli_version baked in
            └─ for each SLO:
                 SLO.sli_name → SLIDefinition(version=SLO.sli_version)
                 → indicators with $process_name, $asset_name, etc.
                 → substitute variables (asset vars + SLO vars + reserved)
                 → ready-to-execute queries
                 → send to prometheus-prod
```

### Evaluation Row Population

The `Evaluation` row stores resolved references for reproducibility. Post-redesign:
- `slo_name`, `slo_version` — from the SLO definition (unchanged)
- `sli_name`, `sli_version` — derived from the SLO definition's `sli_name` and `sli_version` (previously derived from the link)
- `data_source_name` — from the link (unchanged)

The evaluation row continues to store all three for auditability. The change is only in where `sli_name`/`sli_version` are resolved from.

### Variable Merge Priority (unchanged from adapter-protocol spec)

```
1. Per-evaluation overrides (trigger request)
2. SLO-level variables (from the specific generated SLO)
3. Asset-level variables (from the asset being evaluated)
4. Reserved variables ($asset_name, $evaluation_name, $start, $end)
```

### Batch Scenario

```
4 VMs × branch-X + 4 VMs × branch-Y
Each attached to "app_x_plugins" group (30 SLOs) via prometheus-prod

Trigger "evaluate all":
  8 assets × 30 SLOs = 240 evaluations
  Each evaluation: resolve SLO → SLI v3 → substitute $asset_name → query prometheus-prod
  Results: 240 independent evaluation rows, comparable across assets
```

---

## 3. Regeneration

Triggered when a group is edited (template change, values added/removed):

### `comparable_from_version` Rules

When regenerating, the system must decide whether existing baselines remain valid for comparison:

| Change | `comparable_from_version` | Rationale |
|---|---|---|
| **Template criteria changed** (pass/warn thresholds, weights) | Preserve existing value | Same queries produce same SLI values; only judgment changed. Baselines remain meaningful for trend analysis. |
| **Template SLI version bumped, queries unchanged** (e.g. only SLI metadata changed) | Preserve existing value | Queries produce identical values. |
| **Template SLI version bumped, queries changed** | Set to new generated version | Different queries produce different values. Old baselines are not comparable. |
| **Template variables changed** (non-`$__gen_` variables) | Set to new generated version | Variable substitution changes query text, so values may differ. |
| **Expansion values added** | N/A (new SLOs, version 1) | Fresh SLO, `comparable_from_version = 1`. |
| **Expansion values removed** | N/A (SLO deactivated) | No new version. History preserved. |

**How to detect "queries changed":** Strict textual comparison of the SLI definition's `indicators` dict at old vs new version. If any query template string differs (even whitespace), queries are considered changed. This is intentionally conservative — false positives (breaking baselines for semantically equivalent queries) are safe; false negatives (preserving baselines when queries actually changed) are not.

### Regeneration Steps

- **Modified SLOs** (template changed): Create new version of each generated SLO with updated objectives/variables/SLI reference. Apply `comparable_from_version` rules above.
- **Values added:** Create new SLO (version 1, `comparable_from_version = 1`). The SLO inherits the group's asset links automatically (evaluated via the group link).
- **Values removed:** Mark generated SLO `active = false`. Evaluation history preserved.
- **Group `version` incremented** on each regeneration.

### SLI Version Bump Cascade

When a new SLI version is published:
1. Templates referencing that SLI show a "new SLI version available" indicator in the UI.
2. User creates a new template version (bumping `sli_version`).
3. This triggers group regeneration — all generated SLOs get new versions with the updated `sli_version`.
4. `comparable_from_version` set per the rules above.

---

## 4. UI Changes

**Reference mockups:** Penpot screenshots in `docs/design inspiration/SLO-generator/`:
- `tree-view-with-groups-and-templates.png` — Sidebar with 3 sections
- `action-options.png` — Create dropdown with 5 items
- `slo-template-creation-wizard.png` — Template wizard (4 steps)
- `slo-group-generator.png` — Group creator with expansion entries
- `warn.png` — Template validation warning (no `$__gen_` vars)

These are the target designs. Implementation should match them closely.

### SLO Wizard (Create/Edit Standard SLO)

Steps change from:

```
Current:                          New:
1. Identity                       1. Identity (name, author, notes)
2. Pick Datasource → Pick SLI     2. Pick SLI (shows adapter_type as context)
3. Indicators & Criteria           3. Indicators & Criteria
4. Comparison & Scoring            4. Comparison & Scoring
```

- Datasource picker removed from wizard entirely — it's a binding-time concern.
- Step 2 shows all active SLI definitions. Each shows its `adapter_type` as a badge.
- **Tag filtering:** SLI definitions use tags for categorization (e.g. `{"category": "resources", "platform": "linux"}`). The wizard shows clickable tag chips above the SLI list. Clicking a chip filters the list to matching SLIs. Multiple chips can be active (AND logic). This is essential at scale — 150 SLIs filtered by `adapter_type` alone is unusable; filtering by `category: "http"` narrows to ~10-15.
- When editing (new version), SLI is pre-selected. If a newer SLI version exists, show a hint: "v4 available, you're on v3".

### Template Wizard (Create/Edit Template SLO)

Same steps as standard wizard, but:
- Name field allows `$__gen_*` placeholders
- Variables section highlights `$__gen_*` entries
- Validation warns if no `$__gen_` variables present
- Submit creates `kind: "template"` SLO

### SLO Group Creator

```
1. Name + display name
2. Pick template (shows SLI + adapter_type as context)
3. Define expansion entries — table with columns per $__gen_ variable, rows per generated SLO
   (columns auto-detected from template's $__gen_ placeholders)
4. Preview: "N SLOs to be generated"
```

No datasource picker — that happens when attaching to an asset. See `slo-group-generator.png` for the table layout.

### Link Dialog (Attach SLO/Group to Asset)

**For standalone SLO:**
```
1. Pick SLO (shows SLI name + adapter_type as read-only context)
2. Pick datasource (filtered to matching adapter_type)
```

**For SLO Group:**
```
1. Pick SLO Group (shows template name + SLI + adapter_type + "N SLOs" as context)
2. Pick datasource (filtered to matching adapter_type)
```

### Sidebar (SLO Mode)

Three sections as shown in the design mockup:

```
STANDARD
  ● web-perf-v3                v3
    ● http-service-sli         6 ind.
      ● prometheus-local
  ● api-latency-v2             v2
  ● payment-sla-v1             v1

TEMPLATES
  ■ plugin-health-tpl          v1
    2 groups
  ■ infra-baseline-tpl         v2
    1 group

GROUPS
  ● app_x_plugins              30 SLOs
    via plugin-health-tpl
  ● infra_nodes                12 SLOs
    via infra-baseline-tpl
```

### Create Dropdown

Five items (matching the design mockup):
1. **SLO Definition** — Standard SLO with criteria (green accent)
2. **SLO Template** — Reusable template for groups (yellow/amber accent)
3. **SLO Group** — Generate SLOs from template (gray accent)
4. **SLI Definition** — Query templates for metrics (purple accent)
5. **Datasource** — Connection to data backend (blue accent)

---

## 5. API Changes

### SLO Definition Endpoints

**Modified:** `POST /slo-definitions`
```json
{
  "name": "web-perf-v3",
  "kind": "standard",
  "sli_name": "http-service-sli",
  "sli_version": 3,
  "objectives": [...],
  ...
}
```

**Modified:** `GET /slo-definitions` — add `kind` filter parameter.
**Modified:** `GET /slo-definitions/{name}` — response includes `sli_name`, `sli_version`, `kind`.

### SLO Group Endpoints (new)

| Endpoint | Method | Purpose |
|---|---|---|
| `/slo-groups` | POST | Create group + generate SLOs |
| `/slo-groups` | GET | List groups |
| `/slo-groups/{name}` | GET | Group detail (includes generated SLO list) |
| `/slo-groups/{name}` | PUT | Update group (triggers regeneration) |
| `/slo-groups/{name}` | DELETE | Deactivate group + generated SLOs + remove `template_bindings` |
| `/slo-groups/{name}/extract` | POST | Extract one generated SLO to standalone |

### Binding Endpoints (modified)

**Modified:** `POST /assets/{name}/slo-bindings` and `POST /asset-groups/{name}/slo-bindings`
```json
{
  "slo_name": "web-perf-v3",
  "data_source_name": "prometheus-prod"
}
```
Note: `sli_name` removed from payload. SLI resolved from SLO definition.

**New:** `POST /assets/{name}/template-bindings` and `POST /asset-groups/{name}/template-bindings`
```json
{
  "template_group_name": "app_x_plugins",
  "data_source_name": "prometheus-prod"
}
```

---

## 6. Database Changes

### Modified Tables

**`slo_definitions`:**
- Add column `kind: VARCHAR NOT NULL DEFAULT 'standard'` (values: `standard`, `template`)
- Add column `sli_name: VARCHAR NOT NULL` (FK-like reference, validated at app level)
- Add column `sli_version: INTEGER NOT NULL`
- Add column `generated_by_group_id: UUID NULL` (FK → `slo_groups.id`). Non-null for generated SLOs, null for standalone/template SLOs. Groups are soft-deleted (`active = false`), so no cascade needed — the FK is for referential integrity and join-based discovery only.

**`asset_slo_links` and `asset_group_slo_links`** — migrated into `slo_bindings`:
- Drop column `sli_name`
- Drop column `link_name`
- Merge both tables into single `slo_bindings` table with `target_type` discriminator
- Preserve `comparison_rules` on rows where `target_type = 'asset'`

### New Tables

**`slo_groups`:**
```sql
CREATE TABLE slo_groups (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR NOT NULL,
  -- partial unique: UNIQUE (name) WHERE active = true
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
```

**`slo_bindings`:** (binds a standalone SLO to an asset or asset group)
```sql
CREATE TABLE slo_bindings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  target_type VARCHAR NOT NULL CHECK (target_type IN ('asset', 'asset_group')),
  target_id UUID NOT NULL,
  slo_name VARCHAR NOT NULL,
  data_source_name VARCHAR NOT NULL,
  comparison_rules JSONB,          -- only used when target_type = 'asset'
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (target_type, target_id, slo_name)
);
```

**`template_bindings`:** (binds a template group to an asset or asset group)
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
```

---

## 7. Migration Path

### Phase 1: Add SLI Reference to SLO (non-breaking)

1. Add `sli_name`, `sli_version`, `kind` columns to `slo_definitions` (nullable initially). Add `generated_by_group_id` (nullable, FK to slo_groups — created later, so add FK constraint in Phase 3).
2. Backfill: for each existing SLO, look up its links to find the SLI used. If all links for an SLO agree on the same SLI, use it. If links disagree (different SLIs for same SLO across assets), add a `migration_conflict` tag to the SLO with details (e.g. `{"migration_conflict": "sli_mismatch: http-sli, alt-sli"}`). The API exposes these via `GET /slo-definitions?tag=migration_conflict` so operators can resolve them. SLOs with no links get `sli_name = NULL` (left for manual assignment via the updated wizard).
3. Make `sli_name` and `sli_version` NOT NULL after backfill is complete and all flagged cases are resolved.
4. Update SLO creation API to require `sli_name` + `sli_version`.
5. Update wizard to stop collecting datasource, start storing `sli_name` on SLO.

### Phase 2: Migrate to `slo_bindings` table (non-breaking)

6. Create `slo_bindings` table.
7. Migrate data from `asset_slo_links` and `asset_group_slo_links` into `slo_bindings` (with `target_type` discriminator). Drop `sli_name` and `link_name` during migration. Preserve `comparison_rules` for asset-level rows.
8. Update binding creation API to use new table, stop requiring `sli_name`.
9. Update binding dialog UI to only show SLO + datasource.
10. Update evaluation trigger to resolve SLI from SLO's `sli_name`/`sli_version`, not from the binding. Evaluation row continues to store `sli_name`/`sli_version` for auditability.

### Phase 3: SLO Templates & Groups

11. Add `kind` column support (already added in Phase 1).
12. Create `slo_groups` table and repository. Add FK constraint on `slo_definitions.generated_by_group_id` → `slo_groups.id` (deferred from Phase 1 since the target table didn't exist yet).
13. Build generator logic (template expansion, regeneration, extraction).
14. Create `template_bindings` table.
15. Wire into API.

### Phase 4: UI

16. Update SLO wizard (remove datasource step).
17. Add template wizard variant.
18. Add SLO Group creator.
19. Update sidebar with three sections.
20. Update create dropdown with five items.
21. Update binding dialog (simplified).

### Phase 5: Cleanup

22. Drop old `asset_slo_links` and `asset_group_slo_links` tables.
23. Remove deprecated API parameters.

Each phase is independently deployable. Phases 1-2 can ship immediately and fix the current UX confusion. Phases 3-5 add the generator capability.
