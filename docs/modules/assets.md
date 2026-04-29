# Assets

## Purpose
TROPEK's asset registry tracks the systems under evaluation — VMs, services,
containers, databases, or any named entity you want to measure. Assets are organized
into groups (flat or hierarchical) and bound to SLO definitions for evaluation.

## Key Concepts

| Concept | What It Is |
|---------|------------|
| **Asset Type** | Extensible vocabulary (vm, service, container, database, endpoint). One type is marked as default. |
| **Asset** | A named entity with a type and key-value labels. Unique by name. |
| **Asset Group** | A named collection of assets and/or other groups. Enables hierarchical organization. |
| **Group Hierarchy** | Groups can contain sub-groups (via asset_group_links). Weights on members/links enable weighted rollup scoring. |
| **SLO Assignment** | Binds an asset or group to a specific SLO definition version plus a DataSource. This is what makes evaluations possible. |
| **SLO Group Assignment** | Binds an SLO group (template) to an asset or group. Creates bindings for all SLOs generated from that template. |
| **Asset Metadata** | Point-in-time snapshots of asset configuration (meta-snapshots). Enables tracking what changed between evaluations. |

## Typical Workflows

### Register assets
1. Create an asset type (or use the default):
   `POST /asset-types {"name": "vm"}`
2. Create an asset with labels:
   `POST /assets {"name": "web-server-01", "type_name": "vm", "tags": {"os": "linux", "env": "prod"}}`
3. Optionally organize into groups:
   `POST /asset-groups {"name": "web-tier", "display_name": "Web Tier"}`
   `POST /asset-groups/web-tier/members {"asset_id": "<uuid>"}`

### Bind SLOs for evaluation
1. Assign an SLO definition version to an asset:
   `PUT /assets/web-server-01/slo-definitions/{slo_definition_id} {"data_source_name": "prometheus-prod"}`
2. Or assign to a group:
   `PUT /asset-groups/web-tier/slo-definitions/{slo_definition_id} {"data_source_name": "prometheus-prod"}`
3. To upgrade an existing assignment to a newer SLO definition version:
   `PATCH /assets/web-server-01/slo-assignments/{assignment_id} {"new_slo_definition_id": "<uuid>"}`

### Bind SLO groups (template-based)
1. Assign an SLO group to an asset:
   `PUT /assets/web-server-01/slo-groups/my-slo-group {"data_source_name": "prometheus-prod"}`
2. Or assign to an asset group:
   `PUT /asset-groups/web-tier/slo-groups/my-slo-group {"data_source_name": "prometheus-prod"}`

## Module Summary

| Endpoint Group | URL Prefix | What It Does |
|----------------|------------|--------------|
| Asset Types | `/asset-types` | CRUD for asset type vocabulary; mark one as default |
| Assets | `/assets` | CRUD for named entities with tags; tag key/value queries |
| Asset Groups | `/asset-groups` | Groups, members, sub-groups, hierarchy tree |
| SLO Assignments | `/assets/{name}/slo-definitions/{slo_definition_id}`, `/asset-groups/{name}/slo-definitions/{slo_definition_id}` | Bind a specific SLO definition version + DataSource to an asset or group |
| SLO Assignment Upgrade | `/assets/{name}/slo-assignments/{assignment_id}` | Upgrade an existing assignment to a new SLO definition version |
| SLO Group Assignments | `/assets/{name}/slo-groups/{slo_group_name}`, `/asset-groups/{name}/slo-groups/{slo_group_name}` | Bind SLO groups (templates) to assets or groups |
| Asset Metadata | `/assets/{asset_id}/meta/snapshots`, `/assets/{asset_id}/meta/timeline`, `/assets/{asset_id}/meta/timeline/summary` | Point-in-time configuration snapshots and timeline queries |

## Gotchas / Design Decisions
- Assets and groups are identified by `name` (human-readable) in most endpoints. UUIDs are internal PKs used only for membership operations and meta-snapshot routes.
- SLO assignments reference a specific `slo_definition_id` (UUID), not just an SLO name. This pins the asset to a concrete versioned definition. Use the upgrade endpoint to advance to a newer version.
- Tags (labels) are JSONB — no schema enforcement, but `GET /assets/tag-keys` and `GET /assets/tag-values` enable filtering across the fleet.
- Group members are added by `asset_id` (UUID), not asset name — look up the asset first to get its ID.
- Group hierarchy supports weighted members and sub-groups for future weighted rollup scoring.
- Asset metadata snapshots are append-only — they record what changed over time, not replace previous state. Query with `from`/`to` time window parameters.
- The `/asset-groups/tree` endpoint must be registered before `/asset-groups/{name}` to avoid the literal string `tree` being treated as a group name. This ordering is enforced in the router.
- Deleting an asset group accepts a `?deactivate_slos=true` query parameter to optionally deactivate linked SLO assignments at deletion time.
