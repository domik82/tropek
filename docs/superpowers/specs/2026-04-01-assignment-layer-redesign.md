# Assignment Layer Redesign + FK Versioning

**Date:** 2026-04-01
**Status:** Draft

## Problem Statement

The current binding architecture has three entangled problems:

1. **Tight coupling between SLO authoring and asset assignment.** `slo_groups` (a registry concept) drives fan-out into `slo_bindings` (an assignment concern). You cannot create SLOs without touching asset binding logic. The `slo_groups` module owns `template_bindings`, which is the wrong module.

2. **`slo_bindings` serves two incompatible jobs.** Direct user-intent rows (`source='direct'`) and system-derived materialisation rows (`source='template'`) live in the same table. The fan-out mechanism (`_fan_out_slo_bindings`, `_sync_template_bindings_for_group`) must stay in sync with the template group state — a fragile write path with partial-failure risk.

3. **Name-based references everywhere.** `slo_bindings.slo_name`, `template_bindings.template_group_name`, `slo_definitions.sli_name` are text references that resolve to "latest" at evaluation time. At 400+ SLOs this means you cannot tell which assets are running outdated SLO/SLI versions, and SLO bumps auto-roll-out without explicit control.

## Design

### Three-Layer Architecture

```
REGISTRY  (authoring, zero asset awareness)
├── sli_definitions        versioned SLI query sets
├── slo_definitions        versioned SLO criteria, FK to specific sli_definition version
├── slo_groups             template generator → creates slo_definitions
└── slo_display_groups     UI navigation buckets (M:N by slo concept name)
    └── slo_display_group_members

ASSIGNMENT  (connects assets to SLOs — no authoring)
├── slo_assignments         asset/group → specific slo_definition version + datasource
└── slo_group_assignments   asset/group → entire slo_group + datasource (always-latest)

ASSETS  (pure asset management, no SLO awareness)
├── assets
├── asset_groups
├── asset_group_members
└── asset_group_links
```

No layer writes into another layer's tables. The evaluation engine reads from Assignment + Registry at trigger time via SQL — no materialised/derived rows anywhere.

### What Gets Removed

| Removed | Replaced by |
|---|---|
| `slo_bindings` table | `slo_assignments` |
| `template_bindings` table | `slo_group_assignments` |
| `source` column | table identity (which table it's in) |
| `template_binding_id` FK | no longer needed |
| `_fan_out_slo_bindings()` | nothing — query-time resolution |
| `_sync_template_bindings_for_group()` | nothing — query-time resolution |
| `slo_definitions.sli_name + sli_version` text refs | `sli_definition_id UUID FK` |
| `slo_groups.template_slo_name + template_slo_version` text refs | `template_slo_definition_id UUID FK` |

---

## Schema Changes

### `sli_definitions` — no structural change

Unchanged. UUID PK, `UNIQUE(name, version)`.

### `slo_definitions` — replace SLI text refs with FK

```sql
-- Remove:  sli_name TEXT, sli_version INTEGER
-- Add:
sli_definition_id  UUID FK → sli_definitions.id  (nullable — null = no SLI linked)
```

`sli_definition_id` pins to a specific SLI version. Null means the SLO has no linked SLI (e.g. push/file mode). The old `sli_name`/`sli_version` columns are dropped; display name is readable via JOIN.

### `slo_groups` — replace template SLO text refs with FK

```sql
-- Remove:  template_slo_name TEXT, template_slo_version INTEGER
-- Add:
template_slo_definition_id  UUID FK → slo_definitions.id  NOT NULL
```

Pins the group to the specific template SLO version it was generated from. When regenerating, a new `template_slo_definition_id` may be supplied.

### `slo_assignments` (new — replaces `slo_bindings`)

```sql
slo_assignments
  id                UUID PK
  asset_id          UUID FK → assets.id        ON DELETE CASCADE  (nullable)
  asset_group_id    UUID FK → asset_groups.id  ON DELETE CASCADE  (nullable)
  CHECK (asset_id IS NULL) != (asset_group_id IS NULL)   -- exactly one target
  slo_definition_id UUID FK → slo_definitions.id  NOT NULL   -- specific version, version-pinned
  slo_name          TEXT NOT NULL   -- denorm from slo_definitions.name, for uniqueness constraint
  data_source_id    UUID FK → data_sources.id     NOT NULL
  comparison_rules  JSONB
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
  UNIQUE (asset_id, slo_name)       WHERE asset_id IS NOT NULL       -- one version per SLO per asset
  UNIQUE (asset_group_id, slo_name) WHERE asset_group_id IS NOT NULL
```

`slo_name` is denormalised from `slo_definitions.name` at insert time and never changes — it exists solely to enforce "at most one version of a given SLO per assignment target". Upgrading an assignment updates `slo_definition_id` in-place; `slo_name` stays the same. No two versions of the same SLO can coexist on the same target.

Only explicit user-created rows. No system-derived rows. Source of truth for "I deliberately want this exact SLO version on this asset."

### `slo_group_assignments` (new — replaces `template_bindings`)

```sql
slo_group_assignments
  id               UUID PK
  asset_id         UUID FK → assets.id        ON DELETE CASCADE  (nullable)
  asset_group_id   UUID FK → asset_groups.id  ON DELETE CASCADE  (nullable)
  CHECK (asset_id IS NULL) != (asset_group_id IS NULL)
  slo_group_id     UUID FK → slo_groups.id    NOT NULL   -- resolves to latest active SLOs at eval time
  data_source_id   UUID FK → data_sources.id  NOT NULL
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
  UNIQUE (asset_id, slo_group_id)       WHERE asset_id IS NOT NULL
  UNIQUE (asset_group_id, slo_group_id) WHERE asset_group_id IS NOT NULL
```

Intentionally always-latest: when a template group gains or loses generated SLOs, all assigned assets automatically reflect the change at the next evaluation trigger. No sync required.

**Asymmetry is intentional:**
- `slo_assignments` = version-pinned ("I own the upgrade")
- `slo_group_assignments` = always-latest ("I trust the SLO authors")

### `slo_display_groups` + `slo_display_group_members` (new)

```sql
slo_display_groups
  id            UUID PK
  name          TEXT UNIQUE NOT NULL
  display_name  TEXT
  parent_id     UUID FK → slo_display_groups.id  (nullable, self-referential hierarchy)
  sort_order    INTEGER NOT NULL DEFAULT 0
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()

slo_display_group_members
  group_id   UUID FK → slo_display_groups.id  ON DELETE CASCADE  NOT NULL
  slo_name   TEXT NOT NULL   -- name-scoped: membership follows the SLO concept, not a specific version
  PRIMARY KEY (group_id, slo_name)
```

Pure registry / UI concern. Zero evaluation-time involvement. SLOs with no membership appear in an "Ungrouped" bucket. Membership is by `slo_name` (concept-scoped) because display groups organise SLOs as concepts, not specific versions.

### `slo_evaluations` — add FK snapshot references

```sql
-- Add (alongside existing slo_name, slo_version, sli_name, sli_version denorm columns):
slo_definition_id  UUID FK → slo_definitions.id  (nullable — backfill not required)
sli_definition_id  UUID FK → sli_definitions.id  (nullable — backfill not required)
```

The denorm text columns (`slo_name`, `slo_version`, `sli_name`, `sli_version`) are kept for Grafana SQL compatibility. The FK columns are set at evaluation creation time and are the canonical reference for joins and trend queries.

---

## Evaluation Resolution (no fan-out)

All resolution happens at trigger time via a single query. Replaces `list_for_asset_evaluation` + `resolve_all_bindings_for_asset`.

```sql
-- Collect all (slo_definition_id, data_source_id) pairs for an asset
-- Inputs: :asset_id, :group_ids (array of asset_group_ids the asset belongs to)

SELECT sa.slo_definition_id, sa.data_source_id, sa.comparison_rules,
       'direct_asset' AS source
FROM slo_assignments sa
WHERE sa.asset_id = :asset_id

UNION ALL

SELECT sa.slo_definition_id, sa.data_source_id, sa.comparison_rules,
       'direct_group' AS source
FROM slo_assignments sa
WHERE sa.asset_group_id = ANY(:group_ids)

UNION ALL

SELECT sd.id AS slo_definition_id, sga.data_source_id, NULL AS comparison_rules,
       'template_asset' AS source
FROM slo_group_assignments sga
JOIN slo_groups sg ON sg.id = sga.slo_group_id AND sg.active = true
JOIN slo_definitions sd ON sd.generated_by_group_id = sg.id AND sd.active = true
WHERE sga.asset_id = :asset_id

UNION ALL

SELECT sd.id AS slo_definition_id, sga.data_source_id, NULL AS comparison_rules,
       'template_group' AS source
FROM slo_group_assignments sga
JOIN slo_groups sg ON sg.id = sga.slo_group_id AND sg.active = true
JOIN slo_definitions sd ON sd.generated_by_group_id = sg.id AND sd.active = true
WHERE sga.asset_group_id = ANY(:group_ids)
```

Deduplication is by **SLO concept name** (not `slo_definition_id`) with precedence `direct_asset > direct_group > template_asset > template_group`. The winning row for each name determines which specific `slo_definition_id` and `data_source_id` is used. The resolution query should JOIN `slo_definitions` to get `sd.name` for grouping:

```sql
WITH all_assignments AS (
  -- ...four UNION ALL arms above, each also selecting sd.name AS slo_name...
)
SELECT DISTINCT ON (slo_name) slo_definition_id, data_source_id, comparison_rules, slo_name
FROM all_assignments
ORDER BY slo_name,
         CASE source
           WHEN 'direct_asset'   THEN 4
           WHEN 'direct_group'   THEN 3
           WHEN 'template_asset' THEN 2
           WHEN 'template_group' THEN 1
         END DESC
```

This ensures that if an asset has a direct `slo_assignments` row for slo-cpu v2 AND a `slo_group_assignments` row that generates slo-cpu v1, only the direct (higher precedence) row is used.

---

## SLO Version Upgrade Workflow

With version-pinned `slo_assignments`, bumping an SLO is an explicit two-step operation:

```
1. Author creates slo_definition v2 (new thresholds, new sli_definition_id if SLI changed)
2. Operator upgrades assignments:
   UPDATE slo_assignments
   SET slo_definition_id = <v2-uuid>
   WHERE slo_definition_id IN (
     SELECT id FROM slo_definitions WHERE name = 'slo-cpu-process-abc' AND version = 1
   )
   -- scope: one asset, a group, or all at once
```

**Stale-assignment query** (visible in UI as "upgrade available"):
```sql
SELECT a.name AS asset_name, sd.name AS slo_name, sd.version AS current_version,
       latest.max_v AS latest_version
FROM slo_assignments sa
JOIN slo_definitions sd ON sd.id = sa.slo_definition_id
JOIN assets a ON a.id = sa.asset_id
JOIN (
  SELECT name, MAX(version) AS max_v
  FROM slo_definitions WHERE active = true GROUP BY name
) latest ON latest.name = sd.name
WHERE sd.version < latest.max_v
ORDER BY sd.name, a.name
```

---

## Module Restructuring

| Concern | Current module | Target module |
|---|---|---|
| `slo_assignments` CRUD | `assets/router.py` + `assets/repository.py` | new `assignments/` module |
| `slo_group_assignments` CRUD | `slo_groups/router.py` | new `assignments/` module |
| `slo_display_groups` CRUD | (new) | new `registry/display_groups/` or within `slo_registry/` |
| Template generation | `slo_groups/` | `slo_groups/` (unchanged, loses all binding code) |

Routes remain asset-centric (`POST /assets/{name}/slo-assignments`) but the repository and service logic lives in `assignments/`.

The `slo_groups` module loses: `TemplateBindingRepository`, `_fan_out_slo_bindings`, `_sync_template_bindings_for_group`, all template-binding route handlers. It becomes a pure SLO template generator.

---

## Migration

No incremental migration needed — this codebase uses `scripts/db-regen-migrations.sh` which regenerates a single `001_initial_schema.py` from current models. The workflow is:

1. Update `api/app/db/models.py` per schema changes above
2. Run `./scripts/db-regen-migrations.sh`
3. Update repositories, routers, trigger resolution
4. Run `just test-int` to verify

No production data to migrate.

---

## Out of Scope (follow-ons)

- `slo_evaluations.data_source_id FK` — the evaluation snapshot keeps `data_source_name` text for now; FK is a follow-on once the assignment layer is stable
- Bulk upgrade API endpoint (`POST /slo-definitions/{name}/upgrade-assignments`)
- `slo_display_groups` UI (tree rendering in navigator)
- Comparison rules on `slo_group_assignments` (currently only on direct assignments)
