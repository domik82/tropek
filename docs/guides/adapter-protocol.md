# Adapter Protocol Guide

A TROPEK adapter is a standalone HTTP service that translates metric queries from
TROPEK's generic format into data-source-specific queries (PromQL, SQL, etc.) and
returns scalar results. The core API never talks to Prometheus or any other backend
directly — it delegates to an adapter and expects a uniform response.

## Required endpoints

### `POST /query`

Accepts an `AdapterQueryRequest` body, returns an `AdapterQueryResponse`.

#### Request

```json
{
  "queries": {
    "response_time_p99": {
      "mode": "raw",
      "query": "histogram_quantile(0.99, ...)"
    },
    "error_rate": {
      "mode": "aggregated",
      "query_template": "rate(errors_total{service=\"$SERVICE\"}[5m])",
      "interval": "1m",
      "methods": ["mean"]
    }
  },
  "variables": {
    "SERVICE": "checkout",
    "TROPEK_ASSET": "my-project/checkout",
    "TROPEK_EVALUATION": "eval-abc123"
  },
  "start": "2026-04-30T10:00:00Z",
  "end":   "2026-04-30T10:10:00Z"
}
```

**Query modes:**

| Mode | Required fields | Returns |
|------|----------------|---------|
| `raw` | `mode`, `query` | One scalar per metric |
| `aggregated` | `mode`, `query_template`, `interval`, `methods` | One scalar per metric.method pair |

**Template variables** — the `variables` map is substituted into query strings before
execution. TROPEK always injects `TROPEK_ASSET`, `TROPEK_EVALUATION`, and the time
range. Additional variables come from the SLO definition.

**Headers** — TROPEK sends `X-Datasource-Name` with the datasource name from the
registry. Adapters may use this for routing or logging.

#### Response

```json
{
  "values": {
    "response_time_p99": 0.312,
    "error_rate": null
  },
  "errors": {
    "error_rate": "no data returned for the given time range"
  },
  "metadata": {
    "response_time_p99": {"sample_count": 60}
  }
}
```

Every metric from the request must appear in `values` or `errors` (or both).
A `null` value in `values` means the metric resolved but returned no data.
The `metadata` field is optional and is not used in scoring — it is for observability.

### `GET /health`

Returns an `AdapterHealthResponse`. Used by TROPEK to check adapter availability
before routing queries.

```json
{
  "status": "ok",
  "datasource": "prometheus"
}
```

`status` must be `"ok"` when the adapter and its backing data source are reachable.

## Writing a Python adapter

Install the shared protocol package, then use the models directly as FastAPI types:

```python
from tropek_adapter_protocol.models import (
    AdapterQueryRequest,
    AdapterQueryResponse,
    AdapterHealthResponse,
)

@app.post('/query', response_model=AdapterQueryResponse)
async def query(request: AdapterQueryRequest) -> AdapterQueryResponse:
    ...

@app.get('/health', response_model=AdapterHealthResponse)
async def health() -> AdapterHealthResponse:
    return AdapterHealthResponse(status='ok', datasource='my-backend')
```

The Pydantic models in `adapters/protocol/tropek_adapter_protocol/models.py` are the
canonical schema definition. Non-Python adapters should treat that file as the
reference specification — field names, types, and nesting are the contract.

## Writing a non-Python adapter

Implement the two endpoints using the JSON shapes above. There is no required
framework or runtime. The only contract is the HTTP interface:

- `POST /query` — accepts and returns the JSON shapes documented above
- `GET /health` — returns `{"status": "ok", "datasource": "<name>"}`

## Registering an adapter as a DataSource

Once the adapter is running, register it with TROPEK via the API:

```http
POST /datasources
Content-Type: application/json

{
  "name": "prod-prometheus",
  "display_name": "Production Prometheus",
  "adapter_type": "prometheus",
  "adapter_url": "http://adapter-prometheus:8081",
  "tags": {"env": "prod"},
  "token": null
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `name` | yes | Unique identifier used in SLO definitions |
| `adapter_type` | yes | Informational label (e.g. `prometheus`, `datadog`) |
| `adapter_url` | yes | Base URL of the adapter — TROPEK appends `/query` and `/health` |
| `display_name` | no | Human-readable label shown in the UI |
| `tags` | no | Arbitrary key-value metadata |
| `token` | no | Bearer token sent to the adapter (stored encrypted) |

After registration, reference the datasource by `name` in SLO YAML files.

## Testing conformance

Use the protocol package's test helper to validate that your adapter returns a
well-formed response:

```python
from tropek_adapter_protocol.testing import assert_query_response_valid

def test_query_endpoint(client):
    response = client.post('/query', json={
        'queries': {
            'my_metric': {'mode': 'raw', 'query': 'up'}
        },
        'variables': {},
        'start': '2026-04-30T10:00:00Z',
        'end':   '2026-04-30T10:10:00Z',
    })
    assert response.status_code == 200
    assert_query_response_valid(response.json())
```

The helper validates structure, required fields, and type correctness. Run it against
both successful and error-returning responses.

## Reference implementation

`adapters/prometheus/` is the production reference adapter. It exposes a job-based
async API on top of the synchronous protocol — queries are submitted as a batch
(`POST /api/v1/query-jobs`), and results are polled (`GET /api/v1/query-jobs/{id}`).
The TROPEK worker handles the polling loop; the adapter just needs to implement
`POST /query` and `GET /health` at a minimum.

See `adapters/prometheus/README.md` for the full implementation notes, including the
rationale for using `httpx` over `requests` and the Redis-backed job queue design.
