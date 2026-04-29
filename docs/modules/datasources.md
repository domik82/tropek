# Data Sources

## Purpose
Data sources are named pointers to adapter instances that know how to fetch metrics.
When an evaluation runs in pull mode, the worker uses the data source's adapter URL
to query for SLI values.

## Key Concepts

| Concept | What It Is |
|---------|------------|
| **Data Source** | A named registration of an adapter instance (name, adapter_type, adapter_url, labels). |
| **Adapter Type** | The kind of metrics backend (e.g., "prometheus", "mock"). Determines which adapter service handles queries. |
| **Adapter URL** | The HTTP endpoint of the adapter service (e.g., `http://adapter-prometheus:8080`). |
| **Query Modes** | Adapters support two modes: raw (complete query sent as-is) and aggregated (template query with server-side aggregation). |
| **Tags** | Arbitrary key/value labels on a data source, queryable via `/datasources/tag-keys` and `/datasources/tag-values`. |
| **Token** | Optional bearer token forwarded to the adapter for authenticated backends. Presence is indicated by `has_token` in responses; the value is never returned. |

## Typical Workflows

### Register an adapter
1. Deploy the adapter service (e.g., Prometheus adapter on :8081).
2. Register it: `POST /datasources {"name": "prometheus-prod", "adapter_type": "prometheus", "adapter_url": "http://adapter-prometheus:8080"}`
3. Bind to an asset via SLO assignment: the `datasource_name` field in the assignment points here.

### Update an adapter URL
`PATCH /datasources/prometheus-prod {"adapter_url": "http://new-host:8080"}`

### Filter data sources by tag
`GET /datasources?tag_key=env&tag_val=production`

### Discover tag usage
- `GET /datasources/tag-keys` — returns all tag keys with usage counts.
- `GET /datasources/tag-values?key=env` — returns all values for the `env` key with counts.

## Module Summary

| Endpoint | Method | What It Does |
|----------|--------|--------------|
| `/datasources` | GET | List all data sources (filterable by `adapter_type`, `tag_key`, `tag_val`) |
| `/datasources` | POST | Register a new data source |
| `/datasources/tag-keys` | GET | Return distinct tag keys with usage counts |
| `/datasources/tag-values` | GET | Return distinct values for a tag key with counts |
| `/datasources/{name}` | GET | Get a single data source by name |
| `/datasources/{name}` | PATCH | Update mutable fields (URL, display name, tags, token) |
| `/datasources/{name}` | DELETE | Remove a data source registration |

## Gotchas / Design Decisions
- Data sources are mutable — URL and labels can be updated. This is intentional: you can point to a new adapter without re-creating bindings.
- The `adapter_type` field is a string, not an enum — new adapter types can be added without code changes.
- `has_token` in the response indicates whether a bearer token is stored, but the token value is never returned from the API.
- For how to build a new adapter, see [../guides/adapter-protocol.md](../guides/adapter-protocol.md).
