# TROPEK Adapter Protocol

Canonical contract for TROPEK data source adapters.

## What is an adapter?

A TROPEK adapter is a standalone HTTP service that translates metric queries from
TROPEK's generic format into data-source-specific queries (PromQL, SQL, etc.) and
returns scalar results.

## Required endpoints

### `POST /query`

Accepts `AdapterQueryRequest`, returns `AdapterQueryResponse`.

See `tropek_adapter_protocol/models.py` for the full schema with field descriptions.

**Query modes:**

| Mode | Spec shape | Returns |
|------|-----------|---------|
| `raw` | `{"mode": "raw", "query": "<promql>"}` | One scalar per metric |
| `aggregated` | `{"mode": "aggregated", "query_template": "...", "interval": "1m", "methods": ["mean"]}` | One scalar per metric.method |

**Headers:** `X-Datasource-Name` -- the datasource name from TROPEK's registry.

### `GET /health`

Returns `AdapterHealthResponse` -- used by TROPEK to check adapter availability.

## Writing a new adapter

1. Install this package: `uv add tropek-adapter-protocol`
2. Use `AdapterQueryRequest` as your FastAPI request model for `POST /query`
3. Return `AdapterQueryResponse` from `POST /query`
4. Use the test helpers to validate conformance:

```python
from tropek_adapter_protocol.testing import assert_query_response_valid

def test_my_adapter(client):
    resp = client.post('/query', json={...})
    assert_query_response_valid(resp.json())
```

## Non-Python adapters

If writing an adapter in Go, Java, etc., use `models.py` as the reference schema.
The Pydantic models map directly to JSON -- field names, types, and nesting are
the contract.
