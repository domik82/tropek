# TROPEK Prometheus SLI Adapter

Async FastAPI service that executes PromQL queries against Prometheus via a Redis-backed job queue with concurrency controls. Queries are submitted as batches, processed asynchronously with semaphore-limited parallelism, and polled for results.

## Stack

| Component | Technology |
|---|---|
| Language | Python 3.13 |
| Framework | FastAPI + uvicorn |
| HTTP client | httpx (async) |
| Job queue | Redis (state + queue) |
| Config | Pydantic Settings (env vars) |
| Logging | structlog |

### Why httpx over requests

httpx was chosen instead of requests because the adapter is fully async (FastAPI + asyncio).
`httpx.AsyncClient` integrates natively with `async/await` — no thread pool workarounds needed.
It also supports ASGI transport, which lets unit tests hit FastAPI routes directly without starting
a real server (see `test_routes.py`). The API surface mirrors requests (`get`, `post`,
`raise_for_status`, `json()`), so there is no learning curve. One HTTP library serves production
code, unit tests, and e2e tests.

## Quick Start

### Docker Compose (full TROPEK stack)

```bash
docker compose up adapter-prometheus
```

Listens on `:8081`. Requires Redis from the main stack.

### Standalone (local dev)

```bash
# Start Redis
docker run -d --name adapter-redis -p 6379:6379 redis:7-alpine

# Start adapter
PROMETHEUS_URL=http://localhost:9090 \
REDIS_URL=redis://localhost:6379/0 \
uv run --directory adapters/prometheus \
    uvicorn tropek_prometheus.main:app --host 0.0.0.0 --port 8081
```

## API Endpoints

### Job lifecycle (v2 protocol)

| Method | Path | Status | Purpose |
|---|---|---|---|
| POST | `/api/v1/query-jobs` | 202 | Submit a batch of SLI queries |
| GET | `/api/v1/query-jobs/{job_id}` | 200 | Poll job status and results |
| DELETE | `/api/v1/query-jobs/{job_id}` | 204 | Cancel a queued/running job |

### Health

| Method | Path | Purpose |
|---|---|---|
| GET | `/health/live` | Liveness probe |
| GET | `/health/ready` | Readiness probe |

### Submit a job

```
POST /api/v1/query-jobs
Content-Type: application/json

{
  "queries": {
    "response_time_p99": {
      "mode": "raw",
      "query": "histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{service=\"$SERVICE\"}[5m])) by (le))"
    },
    "error_rate": {
      "mode": "raw",
      "query": "sum(rate(http_errors_total{service=\"$SERVICE\"}[5m])) / sum(rate(http_requests_total{service=\"$SERVICE\"}[5m]))"
    }
  },
  "variables": {"SERVICE": "api"},
  "start": "2026-03-15T10:00:00Z",
  "end": "2026-03-15T10:30:00Z",
  "timeout_seconds": 60
}

Response 202:
{
  "job_id": "a1b2c3d4-...",
  "status": "queued",
  "created_at": "2026-03-15T10:30:05Z",
  "poll_url": "/api/v1/query-jobs/a1b2c3d4-...",
  "total_queries": 2
}
```

### Poll results

```
GET /api/v1/query-jobs/{job_id}

Response 200 (completed):
{
  "job_id": "a1b2c3d4-...",
  "status": "completed",
  "completed_at": "2026-03-15T10:30:06Z",
  "duration_ms": 842,
  "results": [
    {"indicator": "response_time_p99", "value": 0.058, "success": true, "message": ""},
    {"indicator": "error_rate", "value": 0.012, "success": true, "message": ""}
  ]
}

Response 200 (running):
{
  "job_id": "a1b2c3d4-...",
  "status": "running",
  "progress": {"total": 10, "completed": 6, "failed": 0}
}
```

### Back-pressure

When the queue is full, submit returns `503` with a `Retry-After` header:

```
HTTP/1.1 503 Service Unavailable
Retry-After: 5

{"error": "queue full"}
```

## Variable Substitution

Queries support `$VARIABLE` placeholders resolved before execution:

| Variable | Source | Example |
|---|---|---|
| User-defined | `variables` dict in request | `$SERVICE` → `"api"` |
| `$DURATION_SECONDS` | Auto-computed from `end - start` | `$DURATION_SECONDS` → `300s` |
| `$interval` | Reserved for aggregated mode (Phase 1) | — |

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8080` | Adapter listen port |
| `PROMETHEUS_URL` | `http://localhost:9090` | Prometheus server URL |
| `PROMETHEUS_USERNAME` | — | Optional basic auth username |
| `PROMETHEUS_PASSWORD` | — | Optional basic auth password |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `REDIS_KEY_PREFIX` | `prom-sli:` | Key namespace in Redis |
| `MAX_CONCURRENT_QUERIES` | `10` | Max parallel Prometheus queries per job |
| `MAX_CONCURRENT_JOBS` | `3` | Max jobs processing simultaneously |
| `MAX_QUEUE_DEPTH` | `100` | Max pending jobs before 503 |
| `MAX_QUERIES_PER_JOB` | `400` | Max queries in a single submit |
| `DEFAULT_JOB_TIMEOUT_SECONDS` | `120` | Default job timeout |
| `MAX_JOB_TIMEOUT_SECONDS` | `600` | Maximum allowed timeout |
| `QUERY_TIMEOUT_SECONDS` | `30` | Per-query HTTP timeout |
| `JOB_RETENTION_SECONDS` | `3600` | TTL for completed job data in Redis |
| `LOG_LEVEL` | `INFO` | Logging level |

## Architecture

```
POST /api/v1/query-jobs
        │
        ▼
  ┌─────────────┐     ┌───────────┐
  │ Job Manager  │────▶│   Redis   │  (job state + queue)
  └─────────────┘     └───────────┘
                            │
                            ▼
                    ┌──────────────┐
                    │ Coordinator  │  (background task, dequeues jobs)
                    └──────────────┘
                            │
                  ┌─────────┼─────────┐
                  ▼         ▼         ▼
            ┌──────────────────────────────┐
            │   Semaphore (max_concurrent) │
            └──────────────────────────────┘
                  │         │         │
                  ▼         ▼         ▼
            ┌──────────┐              ┌──────────┐
            │ Strategy │  ...         │ Strategy │
            │  (raw)   │              │  (raw)   │
            └──────────┘              └──────────┘
                  │                         │
                  ▼                         ▼
            ┌────────────────────────────────────┐
            │        Prometheus HTTP Client       │
            │     (instant query at end time)     │
            └────────────────────────────────────┘
                            │
                            ▼
                      ┌────────────┐
                      │ Prometheus │
                      └────────────┘
```

### Key files

```
tropek_prometheus/
├── main.py                     # App factory with lifespan (Redis, coordinator)
├── config.py                   # Pydantic Settings from env vars
├── api/
│   ├── routes.py               # POST/GET/DELETE /api/v1/query-jobs
│   └── schemas.py              # Request/response Pydantic models
├── core/
│   ├── job_manager.py          # Submit, poll, cancel with back-pressure
│   ├── coordinator.py          # Background worker, dequeue + fan-out
│   ├── prometheus_client.py    # Async httpx wrapper for Prometheus API
│   ├── variable_substitutor.py # $VARIABLE replacement in PromQL
│   └── strategies/
│       ├── base.py             # QueryStrategy protocol
│       └── raw.py              # Instant query execution (Phase 0)
├── redis/
│   ├── client.py               # Connection pool factory
│   └── repository.py           # Job state CRUD on Redis keys
└── health/
    └── routes.py               # /health/live, /health/ready
```

## Tests

```bash
# Unit tests (49 tests, no infrastructure needed)
uv run --directory adapters/prometheus pytest tests/ -v

# Live end-to-end smoke test (needs Prometheus + Redis)
./scripts/live-test-adapter.sh
```

### Live test prerequisites

1. Observability stack with data: `cd observability_stack/integration-test && just up`
2. Redis on localhost:6379: `docker run -d --name adapter-redis -p 6379:6379 redis:7-alpine`

The live test starts the adapter, submits jobs (single query, multi-query, variables,
error handling, cancel, DURATION_SECONDS), polls for results, and reports pass/fail.

## Query Modes

| Mode | Phase | Description |
|---|---|---|
| `raw` | 0 (current) | Complete PromQL executed as instant query at `end` timestamp |
| `aggregated` | 1 (planned) | Template + `query_range` + statistical aggregation (mean, p99, etc.) |

## Roadmap

- **Phase 0** (current): Raw-mode queries, async job queue, v2 protocol
- **Phase 1a**: Aggregated query strategy (`query_range` + chunking + stats)
- **Phase 1b**: UI for selecting aggregation methods
- **Phase 2**: SLO template method expansion
- **Phase 3**: Reference docs + Grafana verification panels
