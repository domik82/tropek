# prometheus-sli-adapter Specification

## Context

Rewriting Keptn's Go-based prometheus-service as a standalone Python FastAPI service. The original service has zero throttling (sequential for loop), zero concurrency, zero timeouts (`context.TODO()`), and is event-driven via NATS. The new service is REST-based, must handle bursts of ~400 queries without overwhelming Prometheus, and uses Redis for job state.

---

## API Contract

### `POST /api/v1/query-jobs` -- Submit query batch

Returns `202 Accepted` with a job GUID immediately.

**Request:**
```json
{
  "prometheus_url": "http://prometheus:9090",
  "start": "2024-01-15T10:00:00Z",
  "end": "2024-01-15T10:05:00Z",
  "queries": [
    {
      "indicator": "response_time_p95",
      "mode": "template",
      "query_template": "histogram_quantile(0.95, sum(rate(http_duration_bucket{job=\"$SERVICE-$PROJECT-$STAGE\"}[$DURATION_SECONDS])))",
      "variables": {
        "PROJECT": "sockshop",
        "STAGE": "production",
        "SERVICE": "carts",
        "DEPLOYMENT": "canary"
      }
    },
    {
      "indicator": "error_rate",
      "mode": "raw",
      "query": "sum(rate(http_requests_total{status=~\"5..\"}[5m])) / sum(rate(http_requests_total[5m]))"
    }
  ],
  "timeout_seconds": 60
}
```

- `prometheus_url` -- required (or falls back to `PROMETHEUS_DEFAULT_URL` env var)
- `start`/`end` -- required, ISO 8601. Instant query executes at `end` timestamp. `start` is used to auto-compute `DURATION_SECONDS` if not in variables.
- `queries` -- 1 to 400 items, two modes:
  - **`template`**: `query_template` + `variables` dict. Service substitutes `$KEY` placeholders. Auto-computes `DURATION_SECONDS` as `ceil(end - start)` with `s` suffix (e.g. `"300s"`).
  - **`raw`**: `query` is a complete PromQL string, no substitution.
- `timeout_seconds` -- optional, capped by `MAX_JOB_TIMEOUT_SECONDS`.

**Response `202`:**
```json
{
  "job_id": "a1b2c3d4-...",
  "status": "queued",
  "created_at": "2024-01-15T10:05:01.123Z",
  "poll_url": "/api/v1/query-jobs/a1b2c3d4-...",
  "total_queries": 2
}
```

**Error responses:** `400` (validation), `503` (queue full, include `Retry-After` header).

### `GET /api/v1/query-jobs/{job_id}` -- Poll results

**While running:**
```json
{
  "job_id": "...",
  "status": "running",
  "progress": { "total": 2, "completed": 1, "failed": 0 }
}
```

**When done:**
```json
{
  "job_id": "...",
  "status": "completed",
  "completed_at": "...",
  "duration_ms": 2333,
  "results": [
    {
      "indicator": "response_time_p95",
      "value": 0.245,
      "success": true,
      "message": "",
      "query_executed": "histogram_quantile(0.95, ...actual substituted query...)"
    },
    {
      "indicator": "error_rate",
      "value": null,
      "success": false,
      "message": "query returned 0 results",
      "query_executed": "sum(rate(...))"
    }
  ]
}
```

**On timeout:** `status: "timed_out"`, partial results included. Completed indicators have values; timed-out ones have `success: false, message: "query timed out"`.

**`404`** if job expired (garbage-collected after `JOB_RETENTION_SECONDS`).

### `DELETE /api/v1/query-jobs/{job_id}` -- Cancel

`204 No Content` on success. `404` if not found. `409` if already terminal.

### Health endpoints

- `GET /health/live` -- process alive, no dependency checks
- `GET /health/ready` -- Redis ping OK + workers active
- `GET /health/startup` -- same as ready, used with longer K8s `failureThreshold`

---

## Job Lifecycle

```
queued --> running --> completed
  |          |
  |          +--> timed_out
  |          |
  |          +--> cancelled
  |
  +--> cancelled
```

- **No `failed` state.** Even if every query errors, job is `completed`. Caller checks per-indicator `success` flags.
- Terminal jobs get a Redis TTL (`JOB_RETENTION_SECONDS`, default 1h).

---

## Queue & Concurrency Architecture

```
POST /query-jobs --> write to Redis (status=queued) --> RPUSH to queue:pending
                                                              |
                                                    Job Coordinator (background asyncio task)
                                                    LPOP from queue:pending
                                                              |
                                                    Fan out queries through shared Semaphore
                                                              |
                                            +--------+--------+--------+
                                            |        |        |        |
                                         Worker1  Worker2  ...  WorkerN  (asyncio tasks)
                                            |        |        |        |
                                         httpx calls to Prometheus
                                            |        |        |        |
                                         Write per-indicator result to Redis hash
```

**Key controls:**
- `MAX_CONCURRENT_QUERIES` (default 10) -- global `asyncio.Semaphore`. With 400 queries and limit 10, only 10 hit Prometheus simultaneously.
- `MAX_CONCURRENT_JOBS` (default 3) -- max jobs being processed at once per instance.
- `MAX_QUEUE_DEPTH` (default 100) -- pending jobs before 503 back-pressure.

**Redis data model:**
| Key | Type | Contents |
|-----|------|----------|
| `prom-sli:job:{id}` | Hash | status, timestamps, prometheus_url, timeout, counts |
| `prom-sli:job:{id}:queries` | List | JSON array of query specs (write-once) |
| `prom-sli:job:{id}:results` | Hash | indicator_name -> JSON result |
| `prom-sli:queue:pending` | List | FIFO of job IDs |

**Horizontal scaling:** Multiple instances share Redis. LPOP is atomic -- no two instances grab the same job. Phase 1 expects single instance; architecture supports scaling without code changes.

---

## Query Execution

1. **Variable substitution** (template mode only):
   - Replace `$KEY` with value from `variables` dict
   - `$LABEL.<key>` convention supported
   - Auto-compute `DURATION_SECONDS` = `ceil(end - start)` + `"s"` suffix if not provided
   - After substitution, reject if any `$[A-Z][A-Z0-9_.]*` patterns remain

2. **Prometheus call**: instant query via `GET /api/v1/query?query=<promql>&time=<end_rfc3339>`
   - HTTP client: `httpx.AsyncClient` with connection pooling, per-job base_url
   - Per-query timeout: `QUERY_TIMEOUT_SECONDS` (default 30s)

3. **Result validation** (matching original Go behavior):
   - `vector` with exactly 1 element -> extract float from `result[0].value[1]`
   - `scalar` -> extract float from `result.value[1]`
   - 0 results -> fail: `"query returned 0 results"`
   - N>1 results -> fail: `"query returned N results, expected exactly 1"`
   - NaN/Inf -> fail

4. **No retries** on query errors (PromQL is deterministic). 1 retry on TCP connection reset only.

---

## Configuration (env vars)

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8080` | Listen port |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `REDIS_KEY_PREFIX` | `prom-sli:` | Key namespace |
| `MAX_CONCURRENT_QUERIES` | `10` | Semaphore limit for Prometheus calls |
| `MAX_CONCURRENT_JOBS` | `3` | Concurrent jobs per instance |
| `MAX_QUEUE_DEPTH` | `100` | Pending jobs before 503 |
| `MAX_QUERIES_PER_JOB` | `400` | Max queries per submission |
| `DEFAULT_JOB_TIMEOUT_SECONDS` | `120` | Default job timeout |
| `MAX_JOB_TIMEOUT_SECONDS` | `600` | Max allowed job timeout |
| `QUERY_TIMEOUT_SECONDS` | `30` | Per-query HTTP timeout |
| `JOB_RETENTION_SECONDS` | `3600` | TTL for completed jobs in Redis |
| `PROMETHEUS_DEFAULT_URL` | (none) | Fallback if prometheus_url omitted |
| `LOG_LEVEL` | `INFO` | Logging level |

---

## Error Handling

Three layers:

1. **Request-level** (synchronous): `400` validation, `503` queue full
2. **Job-level**: `timed_out` or `cancelled` (never generic `failed`)
3. **Per-indicator**: `success: false` + `message`. Covers: substitution errors, HTTP errors, bad result cardinality, NaN, timeout, connection errors

Prometheus totally unreachable = all indicators `success: false`, job still `completed`. Caller detects by checking results.

Redis unavailable = `503` on all endpoints, readiness probe fails.

---

## Project Layout

```
prometheus-sli-adapter/
  app/
    __init__.py
    main.py                    # FastAPI app, lifespan, middleware
    config.py                  # Pydantic Settings from env vars
    api/
      routes.py                # POST/GET/DELETE endpoints
      schemas.py               # Pydantic request/response models
    core/
      job_manager.py           # Job creation, status reads, cancellation
      coordinator.py           # Background task: picks jobs, fans out via semaphore
      worker.py                # Single query: substitution + HTTP + result parsing
      prometheus_client.py     # httpx async Prometheus API wrapper
      variable_substitutor.py  # $VARIABLE replacement logic
    redis/
      client.py                # Connection pool management
      repository.py            # Job/result CRUD on Redis keys
    health/
      routes.py                # /health/* endpoints
      checks.py                # Health check functions
  tests/
    test_api/
    test_core/
    test_redis/
  Dockerfile
  pyproject.toml
```

---

## Build Order

1. Config + health endpoints + app skeleton (deployable stub)
2. Redis repository layer (test with `fakeredis`)
3. Variable substitutor (pure logic, unit-testable)
4. Prometheus client (`httpx` + `respx` mocks)
5. Worker (substitutor + client combined)
6. Coordinator + job manager (lifecycle, semaphore, timeouts)
7. API routes (wire everything)
8. Integration tests (Docker Compose with Redis + mock Prometheus)

---

## Verification

- Unit tests: substitutor, result parsing, job state machine
- Integration tests: submit batch -> poll -> verify results (mock Prometheus with `respx` or `wiremock`)
- Load test: submit 400-query batch, verify only `MAX_CONCURRENT_QUERIES` hit Prometheus simultaneously
- Timeout test: submit job with 5s timeout, mock Prometheus to sleep 10s, verify `timed_out` with partial results
- Queue pressure test: fill queue to `MAX_QUEUE_DEPTH`, verify next POST returns `503`
