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

**`timeout_seconds` (request, optional).** The caller's budget in seconds: how long it will wait for the
answer. An adapter should finish (or give up) within it and may cap it at its own maximum. TROPEK's worker
sends its HTTP timeout minus 30 s (at least 30). An adapter that ignores the field keeps working, but a slow
answer then reaches the worker as a read timeout instead of a clean error.

**`error_kinds` (response, optional).** Classifies each entry of `errors` as `transient` (retrying may
succeed: the source timed out, was overloaded, or part of the window could not be fetched) or `data`
(retrying cannot help: a bad query, no data). Every key must also be in `errors`; a missing key, or no
`error_kinds` at all, means `data`. TROPEK applies one rule: **any `transient` metric fails the whole fetch**
and the evaluation job is retried later, regardless of how many other metrics succeeded; with only `data`
errors the evaluation runs and the errored metrics score `error`. Never report a value computed from partial
data; report it as a `transient` error instead.

**Status codes the worker relies on.** Answer `200` with `values` / `errors` / `error_kinds` whenever the
query ran, even if every metric failed. For "try again later", use:

| Status | Meaning | TROPEK's worker |
|---|---|---|
| `429` | too many requests | retries the HTTP call |
| `502` | the adapter could not reach its source | retries the HTTP call |
| `503` | the adapter's queue is full, or the job was cancelled while the caller waited | retries the HTTP call |
| `504` | no answer within the budget | a plain 504 is retried over HTTP; a 504 with a JSON body whose `detail` mentions the budget (the adapter already waited the whole budget) is not, and the evaluation job is retried later instead |

Send `Retry-After` (in seconds) with these; the worker waits that long (at most 60 s) before its next HTTP
attempt, and falls back to exponential backoff when the header is missing or not a number. HTTP retries stop
when a whole new attempt would no longer fit before the evaluation job's deadline; the job is then retried.
Any other `4xx` (for example `400` or `422` for a malformed request) is final: the evaluation is stored
`failed` without a retry. Other `5xx` codes and a `2xx` whose body is not a valid `AdapterQueryResponse` are
not retried over HTTP; the former is retried by the job, the latter fails the evaluation.

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
