# Data Sources

## Purpose

Data sources are named pointers to adapter instances that know how to fetch metrics.
When an evaluation runs in pull mode, the worker uses the data source's adapter URL
to query for SLI values. Data sources are also referenced by
[SLO assignments](registries.md#assignments) to bind a specific adapter to each
asset-SLO pair.

## Key Concepts

| Concept | What It Is |
|---------|------------|
| **Data Source** | A named registration of an adapter instance (name, adapter_type, adapter_url, tags). |
| **Adapter Type** | The kind of metrics backend (e.g., `"prometheus"`, `"mock"`). A free-form string -- new adapter types can be added without code changes. |
| **Adapter URL** | The HTTP endpoint of the adapter service (e.g., `http://adapter-prometheus:8080`). |
| **Token** | Optional bearer token forwarded to the adapter for authenticated backends. The token value is never returned from the API -- only `has_token: bool` is exposed. |
| **Tags** | Arbitrary key/value labels for filtering and grouping. Queryable via `/datasources/tag-keys` and `/datasources/tag-values`. |

## How Data Sources Differ from Registries

Unlike [SLO and SLI definitions](registries.md), data sources are **not versioned**:

- They support in-place updates via `PATCH` (URL, display name, tags, token).
- Deletion is a hard delete, not a soft deactivate.
- There is no version history or `comparable_from_version` tracking.

This is intentional: you can re-point a data source to a new adapter URL without
re-creating all SLO assignment bindings that reference it.

## Typical Workflows

### Register an adapter

1. Deploy the adapter service (e.g., Prometheus adapter on port 8081).
2. Register it:
   `POST /datasources {"name": "prometheus-prod", "adapter_type": "prometheus", "adapter_url": "http://adapter-prometheus:8080"}`
3. Bind to an asset via SLO assignment: the `data_source_name` field in the assignment
   points here. See [Assets -- Bind SLOs](assets.md#bind-slos-for-evaluation).

### Update an adapter URL

`PATCH /datasources/prometheus-prod {"adapter_url": "http://new-host:8080"}`

### Filter data sources by tag

`GET /datasources?tag_key=env&tag_val=production`

### Discover tag usage

- `GET /datasources/tag-keys` -- returns all tag keys with usage counts.
- `GET /datasources/tag-values?key=env` -- returns all values for the `env` key with counts.

## Endpoints

| Method | Path | What It Does |
|--------|------|--------------|
| `GET` | `/datasources` | List all data sources (filterable by `adapter_type`, `tag_key`, `tag_val`). |
| `POST` | `/datasources` | Register a new data source. |
| `GET` | `/datasources/tag-keys` | Return distinct tag keys with usage counts. |
| `GET` | `/datasources/tag-values` | Return distinct values for a tag key with counts. |
| `GET` | `/datasources/{name}` | Get a single data source by name. |
| `PATCH` | `/datasources/{name}` | Update mutable fields (adapter_url, display_name, tags, token). |
| `DELETE` | `/datasources/{name}` | Remove a data source registration (hard delete). |

## Source Code Layout

```
api/tropek/modules/datasource/
    params.py       # DataSourceCreateParams
    repository.py   # DataSourceRepository (non-versioned CRUD, TagQueryMixin)
    router.py       # FastAPI endpoints
    schemas.py      # DataSourceCreate, DataSourceUpdate, DataSourceRead
```

The repository uses `TagQueryMixin` for tag-key and tag-value queries, sharing the
same implementation as the SLO, SLI, and Asset registries.

## Gotchas / Design Decisions

- Data sources are mutable -- URL and labels can be updated in place. This avoids needing to re-create assignment bindings when an adapter moves.
- The `adapter_type` field is a string, not an enum -- new adapter types can be added without code changes.
- `has_token` in the response indicates whether a bearer token is stored. The actual token string is never returned by the API. The `has_token` field is set by a router helper function (`_ds_read()`), not by the ORM model.
- The repository does not use Redis caching (unlike SLO, SLI, and Asset repositories).
- For how to build a new adapter, see [../guides/adapter-protocol.md](../guides/adapter-protocol.md).
