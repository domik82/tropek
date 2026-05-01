# Assets

## Purpose

TROPEK's asset registry tracks the systems under evaluation -- VMs, services,
containers, databases, or any named entity you want to measure. Assets are organized
into groups (flat or hierarchical) and bound to SLO definitions for evaluation.

## Key Concepts

| Concept | What It Is |
|---------|------------|
| **Asset Type** | Extensible vocabulary (vm, service, container, database, endpoint). One type is marked as default. |
| **Asset** | A named entity with a type, key-value tags, template variables, and a display color. Unique by name. |
| **Asset Group** | A named collection of assets and/or other groups. Enables hierarchical organization. |
| **Group Hierarchy** | Groups can contain sub-groups (via `AssetGroupLink`). Members and links carry weights for future rollup scoring. |
| **SLO Assignment** | Binds an asset or group to a specific SLO definition version plus a [data source](datasources.md). This is what makes evaluations possible. |
| **SLO Group Assignment** | Binds an [SLO group](slo-groups.md) (template) to an asset or group. Creates bindings for all SLOs generated from that template. |
| **Comparison Rules** | Per-assignment rules controlling baseline selection. See [Registries -- Comparison Rules](registries.md#comparison-rules). |

## Asset Types

Asset types are a simple vocabulary table. Operations:

- **Create**: `POST /asset-types {"name": "vm"}`
- **Set default**: `POST /asset-types/{name}/default` -- atomically unsets all others.
- **Rename**: `PATCH /asset-types/{old_name} {"name": "new_name"}` -- cascades to all assets.
- **Delete**: only succeeds if no assets reference the type (`ConflictError` if in use).
- **Counts**: `GET /asset-types/counts` -- number of assets per type.

## Asset Groups

Groups organize assets into named collections with optional hierarchy.

### Group Hierarchy

Groups can contain both direct asset members and sub-groups:

- **Members**: assets added by UUID via `POST /asset-groups/{name}/members`.
- **Sub-groups**: other groups linked via `POST /asset-groups/{name}/subgroups`.
- **Tree view**: `GET /asset-groups/tree` returns the full hierarchy, identifying
  top-level groups (those not contained by any other group).

Sub-group traversal is implemented in Python (recursive queries, one per level),
not as a SQL recursive CTE.

### Group Colors

When no color is specified at creation, a random color is chosen from a fixed 10-color
palette. There is no uniqueness check -- two groups may receive the same color.

### Group Deletion

`DELETE /asset-groups/{name}` deletes the group and all its descendant sub-groups.
The `?deactivate_slos=true` query parameter is accepted for API compatibility but
currently has no effect -- SLO deactivation is handled via the assignment layer.

## Asset Service

`AssetService` (in `assets/service.py`) resolves `asset_name` or `group_name` strings
into a `ResolvedAssetScope(asset_id, asset_ids)` for downstream query scoping. When
given a group name, it collects all member asset IDs. This is used by query endpoints
that need to scope results to an asset or group.

## Typical Workflows

### Register assets

1. Create an asset type (or use the default):
   `POST /asset-types {"name": "vm"}`
2. Create an asset with tags and variables:
   `POST /assets {"name": "web-server-01", "type_name": "vm", "tags": {"os": "linux", "env": "prod"}}`
3. Optionally organize into groups:
   `POST /asset-groups {"name": "web-tier", "display_name": "Web Tier"}`
   `POST /asset-groups/web-tier/members {"asset_id": "<uuid>"}`

### Bind SLOs for evaluation

1. Assign an SLO definition version to an asset:
   `PUT /assets/web-server-01/slo-definitions/{slo_definition_id} {"data_source_name": "prometheus-prod"}`
2. Or assign to a group (all members inherit the assignment at lower priority):
   `PUT /asset-groups/web-tier/slo-definitions/{slo_definition_id} {"data_source_name": "prometheus-prod"}`
3. To upgrade an existing assignment to a newer SLO definition version:
   `PATCH /assets/web-server-01/slo-assignments/{assignment_id} {"new_slo_definition_id": "<uuid>"}`

### Bind SLO groups (template-based)

1. Assign an SLO group to an asset:
   `PUT /assets/web-server-01/slo-groups/my-slo-group {"data_source_name": "prometheus-prod"}`
2. Or assign to an asset group:
   `PUT /asset-groups/web-tier/slo-groups/my-slo-group {"data_source_name": "prometheus-prod"}`

## Endpoints

### Asset Types

| Method | Path | What It Does |
|--------|------|--------------|
| `POST` | `/asset-types` | Create a new asset type. |
| `GET` | `/asset-types` | List all asset types. |
| `POST` | `/asset-types/{name}/default` | Set this type as the default (unsets others). |
| `PATCH` | `/asset-types/{name}` | Rename an asset type (cascades to assets). |
| `DELETE` | `/asset-types/{name}` | Delete a type (fails if in use). |
| `GET` | `/asset-types/counts` | Count of assets per type. |

### Assets

| Method | Path | What It Does |
|--------|------|--------------|
| `POST` | `/assets` | Create a new asset. |
| `GET` | `/assets` | List all assets (filterable by `type_name`, `tag_key`, `tag_val`). |
| `GET` | `/assets/tag-keys` | Return distinct tag keys with usage counts. |
| `GET` | `/assets/tag-values` | Return distinct values for a tag key. |
| `GET` | `/assets/{name}` | Get a single asset by name. |
| `PATCH` | `/assets/{name}` | Update mutable fields (tags, variables, color, display name). |
| `DELETE` | `/assets/{name}` | Delete an asset and remove all group membership references. |

### Asset Groups

| Method | Path | What It Does |
|--------|------|--------------|
| `POST` | `/asset-groups` | Create a new group (with optional initial members and subgroups). |
| `GET` | `/asset-groups` | List all groups. |
| `GET` | `/asset-groups/tree` | Full hierarchy tree (top-level groups with nested children). |
| `GET` | `/asset-groups/{name}` | Get a group with its members and subgroups. |
| `PATCH` | `/asset-groups/{name}` | Update group metadata. |
| `DELETE` | `/asset-groups/{name}` | Delete group and all descendant subgroups. |
| `POST` | `/asset-groups/{name}/members` | Add an asset member (by UUID). |
| `DELETE` | `/asset-groups/{name}/members/{asset_id}` | Remove an asset member. |
| `POST` | `/asset-groups/{name}/subgroups` | Link a sub-group. |
| `DELETE` | `/asset-groups/{name}/subgroups/{subgroup_name}` | Unlink a sub-group. |

### SLO Assignments (on assets and groups)

| Method | Path | What It Does |
|--------|------|--------------|
| `GET` | `/assets/{name}/slo-definitions` | List SLO assignments for an asset. |
| `PUT` | `/assets/{name}/slo-definitions/{slo_definition_id}` | Upsert an SLO assignment on an asset. |
| `DELETE` | `/assets/{name}/slo-definitions/{assignment_id}` | Remove an SLO assignment. |
| `PATCH` | `/assets/{name}/slo-assignments/{assignment_id}` | Upgrade to a newer SLO version. |
| `GET` | `/asset-groups/{name}/slo-definitions` | List SLO assignments for a group. |
| `PUT` | `/asset-groups/{name}/slo-definitions/{slo_definition_id}` | Upsert an SLO assignment on a group. |
| `DELETE` | `/asset-groups/{name}/slo-definitions/{assignment_id}` | Remove an SLO assignment from a group. |

### SLO Group Assignments (on assets and groups)

| Method | Path | What It Does |
|--------|------|--------------|
| `GET` | `/assets/{name}/slo-groups` | List SLO group assignments for an asset. |
| `PUT` | `/assets/{name}/slo-groups/{slo_group_name}` | Upsert an SLO group assignment on an asset. |
| `DELETE` | `/assets/{name}/slo-groups/{assignment_id}` | Remove an SLO group assignment. |
| `GET` | `/asset-groups/{name}/slo-groups` | List SLO group assignments for a group. |
| `PUT` | `/asset-groups/{name}/slo-groups/{slo_group_name}` | Upsert an SLO group assignment on a group. |
| `DELETE` | `/asset-groups/{name}/slo-groups/{assignment_id}` | Remove an SLO group assignment from a group. |

## Source Code Layout

```
api/tropek/modules/assets/
    comparison_rules.py  # ComparisonRule model + validate_comparison_rules()
    params.py            # AssetCreateParams, AssetGroupCreateParams
    repository.py        # AssetTypeRepository, AssetRepository, AssetGroupRepository
    router.py            # FastAPI endpoints for types, assets, groups
    schemas.py           # Request/response models for types, assets, groups
    service.py           # AssetService (name-to-UUID resolution)

api/tropek/modules/assignments/
    repository.py        # AssignmentRepository (SLO + SLO group CRUD, resolve_for_asset)
    router.py            # 22 endpoints for assignment management
    schemas.py           # SLOAssignmentUpsert/Read, SLOGroupAssignmentUpsert/Read
```

## Gotchas / Design Decisions

- Assets and groups are identified by `name` (human-readable) in most endpoints. UUIDs are internal PKs used only for membership operations and meta-snapshot routes.
- SLO assignments reference a specific `slo_definition_id` (UUID), not just an SLO name. This pins the asset to a concrete versioned definition. Use the upgrade endpoint to advance to a newer version.
- Tags are JSONB with no schema enforcement, but tag-key and tag-value endpoints enable fleet-wide filtering.
- Group members are added by `asset_id` (UUID), not asset name -- look up the asset first.
- The `/asset-groups/tree` endpoint must be registered before `/asset-groups/{name}` to avoid the literal string `tree` being treated as a group name. This ordering is enforced in the router.
- Deleting an asset hard-deletes it and removes all `AssetGroupMember` rows referencing it, with cache invalidation on both `asset:{id}` and `asset:name:{name}`.
- Assignment PUT endpoints validate that the referenced SLO definition, data source, and target asset/group all exist before creating the assignment.
- SLO group assignments do not support `comparison_rules` (always `None`) and have no upgrade endpoint.
- For how assignment resolution determines which SLOs apply to an asset at evaluation time, see [Registries -- Assignment Resolution](registries.md#assignment-resolution-4-tier-priority).
