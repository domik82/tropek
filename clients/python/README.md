# TROPEK Python Client

Typed Python client and CLI for the TROPEK quality gate API. Provides a programmatic
interface to all TROPEK resources and a declarative YAML manifest system for
infrastructure-as-code workflows.

## Installation

Requires Python 3.13+. Install from the local package:

```bash
cd clients/python
uv pip install -e .
```

Dependencies: `httpx`, `pydantic`, `pyyaml`, `click`.

## Quick Start

```python
from tropek_client import TropekClient

with TropekClient('http://localhost:8080', api_key='my-key') as client:
    # Check connectivity
    client.health()

    # Create an asset and trigger an evaluation
    client.assets.create('web-api', type_name='service', tags={'env': 'prod'})
    result = client.evaluations.evaluate(
        asset_name='web-api',
        eval_name='release-42',
        period_start='2024-01-01T00:00:00Z',
        period_end='2024-01-01T01:00:00Z',
    )
```

## Configuration

| Parameter | Default | Description |
|---|---|---|
| `base_url` | (required) | TROPEK API base URL |
| `api_key` | `None` | Bearer token for authentication |

The client uses a 30-second timeout. The underlying `httpx.Client` is closed
automatically when using the context manager.

## Client API Reference

The client exposes resource-specific namespaces as attributes on `TropekClient`.

### `client.health() -> dict`

Returns API health status.

### Asset Types — `client.asset_types`

| Method | Returns | Description |
|---|---|---|
| `list()` | `list[AssetType]` | List all asset types |
| `create(name, *, is_default=False)` | `AssetType` | Create an asset type |
| `set_default(name)` | `AssetType` | Set a type as default |
| `rename(name, new_name)` | `AssetType` | Rename a type |
| `delete(name)` | `None` | Delete a type |

### Assets — `client.assets`

| Method | Returns | Description |
|---|---|---|
| `list(*, type_name=, tag_key=, tag_val=)` | `PagedResponse[Asset]` | List with optional filters |
| `create(name, type_name='vm', *, display_name=, tags=, variables=)` | `Asset` | Create an asset |
| `get(name)` | `Asset` | Get by name |
| `update(name, **kwargs)` | `Asset` | Partial update |
| `delete(name)` | `None` | Delete an asset |
| `tag_keys()` | `list[dict]` | Distinct tag keys with counts |
| `tag_values(key)` | `list[dict]` | Values for a tag key |

### Asset Groups — `client.asset_groups`

| Method | Returns | Description |
|---|---|---|
| `list()` | `PagedResponse[AssetGroup]` | List all groups |
| `tree()` | `AssetGroupTree` | Get hierarchical tree |
| `create(name, *, display_name=, members=, subgroups=)` | `AssetGroup` | Create a group |
| `get(name)` | `AssetGroup` | Get by name |
| `add_member(group_name, asset_id, weight=1.0)` | `AssetGroup` | Add asset to group |
| `remove_member(group_name, asset_id)` | `None` | Remove asset from group |
| `add_subgroup(group_name, child_group_id, weight=1.0)` | `AssetGroup` | Nest a group |
| `remove_subgroup(group_name, child_group_id)` | `None` | Remove nested group |

### Data Sources — `client.datasources`

| Method | Returns | Description |
|---|---|---|
| `list(*, adapter_type=)` | `PagedResponse[DataSource]` | List with optional filter |
| `create(name, adapter_type, adapter_url, **kwargs)` | `DataSource` | Register a datasource |
| `get(name)` | `DataSource` | Get by name |
| `update(name, **kwargs)` | `DataSource` | Partial update |
| `delete(name)` | `None` | Delete a datasource |
| `tag_keys()` | `list[dict]` | Distinct tag keys |
| `tag_values(key)` | `list[dict]` | Values for a tag key |

### SLI Definitions — `client.slis`

| Method | Returns | Description |
|---|---|---|
| `list()` | `PagedResponse[SLIDefinition]` | List all SLIs |
| `create(body)` | `SLIDefinition` | Create (or new version) |
| `get(name)` | `SLIDefinition` | Get latest version |
| `versions(name)` | `list[SLIDefinition]` | All versions |
| `delete(name)` | `None` | Delete an SLI |
| `new_version(name, **overrides)` | `SLIDefinition` | Create new version with overrides |
| `tag_keys()` | `list[dict]` | Distinct tag keys |
| `tag_values(key)` | `list[dict]` | Values for a tag key |

### SLO Definitions — `client.slos`

| Method | Returns | Description |
|---|---|---|
| `list()` | `PagedResponse[SLODefinition]` | List all SLOs |
| `create(body)` | `SLODefinition` | Create (or new version) |
| `get(name)` | `SLODefinition` | Get latest version |
| `versions(name)` | `list[SLODefinition]` | All versions |
| `delete(name)` | `None` | Delete an SLO |
| `new_version(name, **overrides)` | `SLODefinition` | Create new version with overrides |
| `validate(body)` | `SLOValidationResult` | Validate without saving |
| `test(body)` | `SLOTestResult` | Dry-run evaluation |
| `tag_keys()` | `list[dict]` | Distinct tag keys |
| `tag_values(key)` | `list[dict]` | Values for a tag key |

### SLO Assignments — `client.slo_assignments`

Pins an asset or group to a specific SLO definition version + datasource.

| Method | Returns | Description |
|---|---|---|
| `create_for_asset(asset_name, slo_definition_id, data_source_name, *, comparison_rules=)` | `SLOAssignment` | Upsert for asset |
| `create_for_group(group_name, slo_definition_id, data_source_name, *, comparison_rules=)` | `SLOAssignment` | Upsert for group |
| `list_for_asset(asset_name)` | `list[SLOAssignment]` | List for asset |
| `list_for_group(group_name)` | `list[SLOAssignment]` | List for group |
| `delete_for_asset(asset_name, slo_definition_id)` | `None` | Delete for asset |
| `delete_for_group(group_name, slo_definition_id)` | `None` | Delete for group |

### SLO Groups — `client.slo_groups`

Template-based SLO generation with variable expansion.

| Method | Returns | Description |
|---|---|---|
| `create(name, template_slo_name, template_slo_version, gen_variables, *, display_name=, tags=, author=)` | `SLOGroup` | Create a group |
| `get(name)` | `SLOGroup` | Get by name |
| `list(*, tag_key=, tag_val=)` | `list[SLOGroup]` | List with optional filters |
| `update(name, *, template_slo_name=, template_slo_version=, gen_variables=, ...)` | `SLOGroup` | Update (triggers regeneration) |
| `delete(name)` | `None` | Deactivate a group |
| `extract(group_name, slo_name, new_name)` | `None` | Extract generated SLO to standalone |

### SLO Group Assignments — `client.slo_group_assignments`

Asset/group to SLO group with always-latest semantics.

| Method | Returns | Description |
|---|---|---|
| `create_for_asset(asset_name, slo_group_name, data_source_name)` | `SLOGroupAssignment` | Upsert for asset |
| `create_for_group(group_name, slo_group_name, data_source_name)` | `SLOGroupAssignment` | Upsert for group |
| `list_for_asset(asset_name)` | `list[SLOGroupAssignment]` | List for asset |
| `list_for_group(group_name)` | `list[SLOGroupAssignment]` | List for group |
| `delete_for_asset(asset_name, slo_group_name)` | `None` | Delete for asset |
| `delete_for_group(group_name, slo_group_name)` | `None` | Delete for group |

### Evaluations — `client.evaluations`

| Method | Returns | Description |
|---|---|---|
| `list(*, asset_name=, slo_name=, result=, date=, group_name=, from_=, to=, limit=50, offset=0)` | `PagedResponse[EvaluationSummary]` | List with filters |
| `get(eval_id)` | `EvaluationDetail` | Full evaluation detail |
| `evaluate(asset_name, eval_name, period_start, period_end, *, variables=)` | `dict` | Trigger evaluation |
| `evaluate_batch(mode, eval_name, *, asset_name=, periods=, asset_names=, period_start=, period_end=, variables=)` | `dict` | Batch trigger (`by_date` or `by_asset`) |
| `invalidate(eval_id, note)` | `EvaluationSummary` | Invalidate an evaluation |
| `restore(eval_id)` | `EvaluationSummary` | Restore invalidated eval |
| `pin_baseline(eval_id, reason, author)` | `EvaluationDetail` | Pin as baseline |
| `unpin_baseline(eval_id)` | `EvaluationDetail` | Remove baseline pin |
| `override_status(eval_id, new_result, reason, author)` | `EvaluationDetail` | Override result |
| `restore_override(eval_id)` | `EvaluationDetail` | Restore original result |
| `re_evaluate_from_date(scope, from_date, *, selector=, slo_version=, dry_run=, pin_strategy=)` | `dict` | Re-evaluate from date |
| `re_evaluate_from_baseline(scope, *, selector=, slo_version=, dry_run=, pin_strategy=)` | `dict` | Re-evaluate from pinned baseline |
| `re_evaluate_from_evaluation(evaluation_id, scope, *, selector=, slo_version=, dry_run=, pin_strategy=)` | `dict` | Re-evaluate from reference eval |

Re-evaluation `scope` is `{'kind': 'asset', 'asset_name': '...'}` or
`{'kind': 'group', 'group_name': '...'}`. `pin_strategy` can be `'skip_to_pin'` or
`'ignore_pin'` to resolve baseline-pin conflicts.

### Annotations — `client.annotations`

| Method | Returns | Description |
|---|---|---|
| `list(eval_id)` | `list[Annotation]` | List for an evaluation |
| `create(eval_id, content, **kwargs)` | `Annotation` | Create SLO-level annotation |
| `create_for_run(run_id, content, **kwargs)` | `Annotation` | Create run-level annotation |
| `update(eval_id, ann_id, **kwargs)` | `Annotation` | Update an annotation |
| `hide(eval_id, ann_id, reason, author=None)` | `Annotation` | Soft-delete |

### Trend — `client.trend`

| Method | Returns | Description |
|---|---|---|
| `by_eval(eval_id, metric, from_, *, to=)` | `list[TrendPoint]` | Trend by evaluation ID |
| `by_asset(asset_name, slo_name, metric, from_, *, to=)` | `list[TrendPoint]` | Trend by asset + SLO |

## Manifest System

The manifest system enables declarative, infrastructure-as-code management of TROPEK
resources using YAML files.

### Manifest Format

Each manifest document has four fields:

```yaml
api_version: tropek/v1
kind: Asset
metadata:
  name: web-api
  display_name: Web API
  tags:
    env: prod
spec:
  type_name: service
```

Supported kinds (processed in dependency order):
`AssetType`, `DataSource`, `Asset`, `SLI`, `SLO`, `AssetGroup`, `SLOGroup`,
`SLOAssignment`, `SLOGroupAssignment`.

A single file can contain multiple documents separated by `---`. You can also point
at a directory — all `*.yaml` and `*.yml` files are loaded.

### SLO Assignment Manifest

```yaml
api_version: tropek/v1
kind: SLOAssignment
metadata:
  name: web-api-latency-assignment
spec:
  target_type: asset        # or asset_group
  target_name: web-api
  slo_name: latency-slo
  data_source_name: prometheus
```

### Reconciliation

The manifest system uses desired-state reconciliation:
1. Load and parse all YAML documents
2. Topologically sort by kind dependency
3. For each document, look up the existing resource via the API
4. Compare fields to detect drift (CREATE / UPDATE / SKIP)
5. Apply changes, blocking dependent kinds on failure

### Programmatic Usage

```python
from tropek_client import TropekClient
from tropek_client.manifest import load_manifests, apply, dry_run

docs = load_manifests('manifests/')

with TropekClient('http://localhost:8080') as client:
    # Preview changes
    plan = dry_run(client, docs)
    for action in plan.actions:
        print(f'{action.operation}  {action.kind}/{action.name}')

    # Apply
    result = apply(client, docs)
    print(f'{result.created} created, {result.updated} updated')
```

## CLI Usage

The CLI is installed as `tropek` (entry point defined in pyproject.toml).

### Validate manifests

```bash
tropek validate -f manifests/
tropek validate -f my-slo.yaml
```

Checks syntax and cross-references without contacting the API.

### Apply manifests

```bash
# Dry run — show what would change
tropek apply --dry-run -f manifests/ --base-url http://localhost:8080

# Apply changes
tropek apply -f manifests/ --base-url http://localhost:8080 --api-key my-key
```

### Export current state

```bash
# To stdout
tropek export --base-url http://localhost:8080

# To file
tropek export -f backup.yaml --base-url http://localhost:8080 --api-key my-key
```

Exports all resources (asset types, datasources, assets, SLIs, SLOs, groups,
assignments) as a multi-document YAML manifest.

## Known Limitations

- **Asset names are globally unique.** There is no per-group scoping — two groups
  cannot each contain an asset named `load_test`. Assets are identified by name
  across the entire TROPEK instance.

## Error Handling

All API errors raise typed exceptions:

| Exception | HTTP Status | When |
|---|---|---|
| `TropekNotFoundError` | 404 | Resource not found |
| `TropekConflictError` | 409 | Resource conflict (duplicate name) |
| `TropekValidationError` | 422 | Request validation failed |
| `TropekAPIError` | any non-2xx | Base class for all errors |

Each exception has `status_code` and `detail` attributes:

```python
from tropek_client import TropekClient, TropekNotFoundError

with TropekClient('http://localhost:8080') as client:
    try:
        client.assets.get('nonexistent')
    except TropekNotFoundError as e:
        print(e.status_code)  # 404
        print(e.detail)       # "asset 'nonexistent' not found"
```
