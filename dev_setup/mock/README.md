# dev_setup/mock

Demo infrastructure for TROPEK — a realistic e-commerce monitoring setup
loaded entirely via real API calls using the typed Python client.

## What it creates

| Kind | Items |
|---|---|
| AssetType | `service`, `database`, `vm` |
| DataSource | `prometheus-local` → `http://localhost:8081` |
| SLI | `http-service-sli`, `db-sli` |
| SLO | `http-availability-slo`, `db-performance-slo` |
| Asset | `checkout-api`, `product-catalog`, `user-service`, `orders-db` |
| AssetGroup | `core-services`, `data-tier`, `ecommerce-prod` |
| AssetSLOLink | one per asset, binding asset → SLO + SLI + datasource |
| AssetGroupSLOLink | one per group, binding group → SLO + SLI + datasource |

## Prerequisites

```bash
# API running at localhost:8080 (and Prometheus adapter at :8081 for evaluations)
docker compose up api timescaledb redis -d
```

## Usage

### Validate (no API calls)

```bash
uv run --directory clients/python tropek validate -f dev_setup/mock/
```

### Dry-run (shows CREATE / UPDATE / SKIP per resource)

```bash
uv run --directory clients/python tropek apply \
  -f dev_setup/mock/ \
  --base-url http://localhost:8080 \
  --dry-run
```

### Apply (creates all resources)

```bash
uv run --directory clients/python tropek apply \
  -f dev_setup/mock/ \
  --base-url http://localhost:8080
```

`apply` is **idempotent** — re-running skips anything that already exists and
only creates new versions of SLOs/SLIs if their content changed.

## Adding group members

The manifest system creates groups without members (member sync is not yet
implemented in the reconciler). Add members via the API after bootstrap:

```bash
# Look up asset IDs
curl http://localhost:8080/assets/checkout-api

# Add to group
curl -X POST http://localhost:8080/asset-groups/core-services/members \
  -H "Content-Type: application/json" \
  -d '{"asset_id": "<uuid>", "weight": 1.0}'
```

## Manifest format

Each YAML file can contain one or more documents separated by `---`.
The loader sorts them topologically (AssetType → DataSource → Asset →
SLI → SLO → AssetGroup → AssetSLOLink → AssetGroupSLOLink), so document
order within files doesn't matter.

```yaml
api_version: tropek/v1
kind: Asset                # one of the eight supported kinds
metadata:
  name: my-service         # required — used as the unique identifier
  display_name: My Service # optional
  labels:                  # optional key/value tags
    team: platform
spec:
  type_name: service       # kind-specific fields
```

See `manifests/slo-definitions.yaml` for the SLO YAML embedding pattern
(`spec.slo_yaml` is a YAML literal block string).

## Change point transitions demo (issue #64)

`cp-transition-monitor` (SLI `cp-transition-sli`, SLO `cp-transition-slo`)
exercises the change-point magnitude fix: appeared/vanished transitions for
zero-mean segments and the local adjacent-segment percent for non-zero
shifts. The mock data is defined in
`adapters/mock/scenarios/change-point-transitions.yaml` — see that file's
header comment for the full how-to-run steps, including regenerating the
CSVs and driving the 61 daily evaluations via
`dev_setup/stages/seed_evaluations.py`.
