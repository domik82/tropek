# TROPEK Prometheus Adapter

Standalone FastAPI service that translates TROPEK SLI queries into PromQL, executes them against a Prometheus server, and returns aggregated metric values.

## Status

Skeleton — only the `/health` endpoint is implemented. The `/query` endpoint is planned.

## Stack

| Component | Technology |
|---|---|
| Language | Python 3.13 |
| Framework | FastAPI + uvicorn |
| HTTP client | httpx (async, for Prometheus API calls) |
| Retries | tenacity |
| Config | Pydantic Settings |
| Logging | structlog |

## Running

### In Docker Compose (with the full stack)

```bash
docker compose up adapter-prometheus
```

Listens on `:8081`. Configured via environment variables in `docker-compose.yml`.

### Standalone (local dev)

```bash
cd adapters/prometheus
uv run uvicorn app.main:app --port 8081 --reload
```

## Endpoints

| Method | Path | Status | Purpose |
|---|---|---|---|
| GET | `/health` | Implemented | `{"status": "ok", "datasource": "prometheus"}` |
| POST | `/query` | Planned | Execute SLI queries against Prometheus |

### Planned `/query` interface

```
POST /query
Content-Type: application/json

{
  "queries": {
    "response_time_p99": "histogram_quantile(0.99, rate(...))",
    "error_rate": "rate(http_requests_total{status=~\"5..\"}[5m])"
  },
  "start": "2026-03-15T10:00:00Z",
  "end": "2026-03-15T10:30:00Z"
}

Response 200:
{
  "values": {
    "response_time_p99": 450.3,
    "error_rate": 0.001
  },
  "errors": {
    "missing_metric": "no data returned for query"
  }
}
```

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `PROMETHEUS_URL` | `http://prometheus:9090` | Prometheus server base URL |
| `QG_ADAPTER_PROMETHEUS_USERNAME` | — | Optional basic auth username |
| `QG_ADAPTER_PROMETHEUS_PASSWORD` | — | Optional basic auth password |

## Architecture

```mermaid
flowchart LR
    API[TROPEK API / Worker] -->|POST /query| AD[Prometheus Adapter :8081]
    AD -->|PromQL via HTTP| P[Prometheus :9090]
    P -->|time-series data| AD
    AD -->|aggregated scalars| API
```

The adapter sits between TROPEK's evaluation worker and Prometheus. It:

1. Receives a map of metric names → PromQL queries plus a time range
2. Executes each query against the Prometheus HTTP API (`/api/v1/query_range`)
3. Aggregates the time-series result into a single scalar per metric
4. Returns values and any per-metric errors

This separation keeps Prometheus-specific logic out of the core API and allows swapping data sources by writing new adapters with the same `/query` interface.

## Project structure

```
adapters/prometheus/
├── app/
│   ├── __init__.py
│   └── main.py          # FastAPI app + /health endpoint
├── tests/
│   └── __init__.py
├── pyproject.toml        # Dependencies (fastapi, httpx, tenacity, structlog)
└── README.md
```

## Tests

```bash
uv run pytest adapters/prometheus/tests/ -v
```
