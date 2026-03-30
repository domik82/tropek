# SLO Groups — Usage Guide

SLO groups generate multiple SLO definitions from a single **template SLO** by expanding variables. This avoids duplicating SLO definitions when the same quality criteria apply to many targets (processes, services, environments).

## Concepts

| Concept | What it is |
|---|---|
| **Template SLO** | An SLO definition with `kind: template` and `$__gen_<key>` placeholders in its name and variables. Lives in `slo-definitions.yaml` like any other SLO. |
| **SLO Group** | References a template SLO + a set of `gen_variables`. Creates one generated SLO per variable row. |
| **Generated SLO** | A normal `kind: standard` SLO created by the group. Behaves identically to a hand-written SLO — it has bindings, triggers evaluations, and stores results. The only difference: it's read-only (changes come from the group). |
| **Template Binding** | Links an SLO group to an asset or asset group with a datasource. When created, it fans out into real `slo_bindings` for each generated SLO — so evaluations work without any special handling. |

## Loading via manifest files (recommended)

The preferred way to provision SLO groups is through YAML manifest files loaded by the Python client. This is how `dev-start.sh` bootstraps the dev environment, and how `bootstrap_tropek` (or any other seed dataset) should do it.

### Where manifest files live

```
bootstrap_mock/manifests/          ← mock/dev seed data
    sli-definitions.yaml
    slo-definitions.yaml           ← template SLOs go here, mixed with standard SLOs
    slo-groups.yaml                ← SLOGroup manifests
    template-bindings.yaml         ← TemplateBinding manifests
    ...

bootstrap_tropek/manifests/        ← production-style seed data (same structure)
    sli-definitions.yaml
    slo-definitions.yaml
    slo-groups.yaml
    template-bindings.yaml
    ...
```

Each file holds one or more YAML documents separated by `---`. Kind can be anything — `load_manifests` reads all files and routes each document by its `kind` field.

### Apply order

The client applies manifests in dependency order automatically:

```
SLI → SLO (template) → SLOGroup → TemplateBinding
```

So you can put all kinds in any file — ordering within files does not matter.

### How dev-start.sh loads them

```
scripts/dev-start.sh
  → scripts/bootstrap.py <api_url>
    → load_manifests("bootstrap_mock/manifests/")   # reads all *.yaml files
    → apply(client, docs)                           # posts each doc to the API
```

To run bootstrap manually against a live API:

```bash
uv run --directory clients/python python ../../scripts/bootstrap.py http://localhost:9080
```

### Full manifest example (41 processes × 1 category)

**`slo-definitions.yaml`** — add the template SLO alongside standard SLOs:

```yaml
---
api_version: tropek/v1
kind: SLO
metadata:
  name: "process/$__gen_process_name/cpu"
spec:
  kind: template
  sli_name: process-metrics-sli
  sli_version: 1
  display_name: "CPU — $__gen_process_name"
  variables:
    process_name: "$__gen_process_name"
    AGGREGATION_WINDOW: "5m"
  total_score:
    pass_pct: 90.0
    warning_pct: 75.0
  objectives:
    - sli: cpu_usage_pct
      pass_criteria: ["<80"]
      warning_criteria: ["<90"]
      weight: 1
      key_sli: true
```

**`slo-groups.yaml`** — one group expands to N SLOs:

```yaml
---
api_version: tropek/v1
kind: SLOGroup
metadata:
  name: all-processes-cpu
spec:
  display_name: All Processes — CPU
  template_slo_name: "process/$__gen_process_name/cpu"
  template_slo_version: 1
  gen_variables:
    process_name:
      - auth
      - cache
      - db
      # ... 41 total
  tags:
    category: cpu
```

**`template-bindings.yaml`** — bind the group to an asset group:

```yaml
---
api_version: tropek/v1
kind: TemplateBinding
metadata:
  name: all-processes-cpu-binding
spec:
  target_type: asset_group
  target_name: production-hosts
  template_group_name: all-processes-cpu
  data_source_name: prometheus-local
```

This produces 41 generated SLOs and 41 `slo_bindings` from three YAML documents — no manual duplication.

---

## Quick Start

### 1. Create a template SLO

A template SLO uses `$__gen_<key>` placeholders in its name and variables. These placeholders are substituted by the group's `gen_variables` during generation.

```yaml
# slo-definitions.yaml
api_version: tropek/v1
kind: SLO
metadata:
  name: "plugin/$__gen_process_name"
spec:
  kind: template
  sli_name: plugin-metrics-sli
  sli_version: 1
  display_name: "Plugin Health — $__gen_process_name"
  variables:
    process_name: "$__gen_process_name"
    AGGREGATION_WINDOW: "5m"
  objectives:
    - sli: cpu_usage
      pass_criteria: ["<80"]
      warning_criteria: ["<90"]
      weight: 1
      key_sli: true
    - sli: memory_usage
      pass_criteria: ["<1073741824"]
      weight: 1
```

The template SLO itself is never evaluated — it's a blueprint.

### 2. Create an SLO group

The group references the template and provides variable values. Each row in `gen_variables` produces one generated SLO.

```yaml
# slo-groups.yaml
api_version: tropek/v1
kind: SLOGroup
metadata:
  name: app-x-plugins
spec:
  display_name: App-X Plugin Monitoring
  template_slo_name: "plugin/$__gen_process_name"
  template_slo_version: 1
  gen_variables:
    process_name: ["auth", "cache", "db"]
  tags:
    app: app-x
```

This generates three SLOs:
- `plugin/auth` with `process_name=auth`
- `plugin/cache` with `process_name=cache`
- `plugin/db` with `process_name=db`

### 3. Bind the group to targets

A template binding connects the group's generated SLOs to an asset or asset group via a datasource. This creates real `slo_bindings` under the hood, so evaluations trigger normally.

```yaml
# template-bindings.yaml
api_version: tropek/v1
kind: TemplateBinding
metadata:
  name: core-services-plugins-binding
spec:
  target_type: asset_group
  target_name: core-services
  template_group_name: app-x-plugins
  data_source_name: prometheus-local
```

After this, `POST /evaluations` with `asset_name=checkout-api` and `slo_name=plugin/auth` works exactly like any other SLO evaluation.

## Multi-Environment Usage

A template SLO is independent from any group — multiple groups can reference the same template. This is the recommended pattern for managing the same SLO criteria across environments.

### Example: TEST and PROD monitoring the same processes

Use a name pattern that includes the environment to avoid name collisions:

```yaml
# Template SLO — shared between environments
api_version: tropek/v1
kind: SLO
metadata:
  name: "plugin/$__gen_env/$__gen_process_name"
spec:
  kind: template
  sli_name: plugin-metrics-sli
  sli_version: 1
  display_name: "Plugin Health — $__gen_env/$__gen_process_name"
  variables:
    process_name: "$__gen_process_name"
    AGGREGATION_WINDOW: "5m"
  objectives:
    - sli: cpu_usage
      pass_criteria: ["<80"]
      warning_criteria: ["<90"]
      weight: 1
      key_sli: true
    - sli: memory_usage
      pass_criteria: ["<1073741824"]
      weight: 1
```

```yaml
# TEST group — monitors auth and cache during testing
api_version: tropek/v1
kind: SLOGroup
metadata:
  name: plugins-test
spec:
  display_name: Plugin Monitoring (TEST)
  template_slo_name: "plugin/$__gen_env/$__gen_process_name"
  template_slo_version: 1
  gen_variables:
    env: ["test", "test"]
    process_name: ["auth", "cache"]
  tags:
    environment: test
```

```yaml
# PROD group — monitors all three processes
api_version: tropek/v1
kind: SLOGroup
metadata:
  name: plugins-prod
spec:
  display_name: Plugin Monitoring (PROD)
  template_slo_name: "plugin/$__gen_env/$__gen_process_name"
  template_slo_version: 1
  gen_variables:
    env: ["prod", "prod", "prod"]
    process_name: ["auth", "cache", "db"]
  tags:
    environment: prod
```

This generates:
- TEST: `plugin/test/auth`, `plugin/test/cache`
- PROD: `plugin/prod/auth`, `plugin/prod/cache`, `plugin/prod/db`

**Deleting the TEST group** deactivates only its generated SLOs (`plugin/test/auth`, `plugin/test/cache`) and its template bindings. The template SLO and the PROD group are completely unaffected.

## Updating a Group

When you update a group (change `gen_variables`, template version, etc.), the regeneration engine computes the minimal set of changes:

- **Added variables** → new SLOs are created
- **Removed variables** → old SLOs are deactivated
- **Criteria-only change** (same SLI queries) → new SLO version, baseline preserved
- **SLI query change** or **template variable change** → new SLO version, baseline reset

Template bindings are automatically synced: new generated SLOs get `slo_bindings`, deactivated ones have theirs removed.

## Extracting a Generated SLO

If a generated SLO needs to diverge from the group (different thresholds, custom criteria), extract it to a standalone SLO:

```
POST /slo-groups/app-x-plugins/extract
{
  "slo_name": "plugin/auth",
  "new_name": "plugin-auth-custom"
}
```

This:
1. Creates a standalone copy (`plugin-auth-custom`) with `kind: standard`
2. Copies template bindings → direct `slo_bindings` for the new SLO
3. Deactivates the original generated SLO
4. Shrinks the group's `gen_variables` (removes the extracted row)

The extracted SLO is now fully independent and can be edited like any other SLO.

## API Reference

### SLO Group endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/slo-groups` | Create group + generate SLOs |
| GET | `/slo-groups` | List groups (optional `tag_key`/`tag_val` filter) |
| GET | `/slo-groups/{name}` | Get group detail |
| PUT | `/slo-groups/{name}` | Update group → regenerate SLOs |
| DELETE | `/slo-groups/{name}` | Deactivate group + generated SLOs |
| POST | `/slo-groups/{name}/extract` | Extract generated SLO to standalone |

### Template Binding endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/assets/{name}/template-bindings` | List bindings for asset |
| POST | `/assets/{name}/template-bindings` | Create binding for asset |
| DELETE | `/assets/{name}/template-bindings/{group_name}` | Delete binding |
| GET | `/asset-groups/{name}/template-bindings` | List bindings for group |
| POST | `/asset-groups/{name}/template-bindings` | Create binding for group |
| DELETE | `/asset-groups/{name}/template-bindings/{group_name}` | Delete binding |

### SLO Binding source field

SLO bindings now have a `source` field:
- `"direct"` — manually created binding
- `"template"` — automatically created by a template binding fan-out

Template-sourced bindings also have a `template_binding_id` linking back to the template binding that created them. The UI uses this to show template-sourced bindings as read-only.
