# Configuration Reference

TROPEK uses two configuration sources:

1. **Environment variables** (prefixed `TK_`) — for secrets and connection strings
2. **`config.yaml`** — for non-secret runtime settings (pool sizes, TTLs, timeouts)

Environment variables always take precedence over `config.yaml` values.

## Environment Variables

### Required

| Variable | Description |
|---|---|
| `TK_DB_PASSWORD` | PostgreSQL password (not needed if `TK_DATABASE_URL` is set) |
| `TK_REDIS_PASSWORD` | Redis password (not needed if `TK_REDIS_URL` is set) |
| `TK_SECRET_KEY` | Application secret key — generate with `openssl rand -hex 32` |

### Database connection

| Variable | Default | Description |
|---|---|---|
| `TK_DATABASE_URL` | — | Full asyncpg URL. If set, overrides all `TK_DB_*` vars below |
| `TK_DB_HOST` | `localhost` | PostgreSQL host |
| `TK_DB_PORT` | `5432` | PostgreSQL port |
| `TK_DB_USER` | — | PostgreSQL user |
| `TK_DB_PASSWORD` | — | PostgreSQL password |
| `TK_DB_NAME` | `tropek` | Database name |
| `TK_DB_POOL_SIZE` | `10` (config.yaml) | Connections kept open **per process** |
| `TK_DB_MAX_OVERFLOW` | `20` (config.yaml) | Extra burst connections **per process** |

### API processes and DB pool sizing

The shipped compose files run the API as several uvicorn processes and give **the `api`
service only** a smaller per-process pool. The worker keeps config.yaml's 10 + 20, which
its `max_jobs: 10` concurrent jobs need.

| Compose variable (`.env`) | Default | Sets on `api` |
|---|---|---|
| `TK_API_WORKERS` | `4` | `WEB_CONCURRENCY` (uvicorn `--workers`) |
| `TK_API_DB_POOL_SIZE` | `5` | `TK_DB_POOL_SIZE` |
| `TK_API_DB_MAX_OVERFLOW` | `5` | `TK_DB_MAX_OVERFLOW` |

Why: a single uvicorn process runs every request on one event loop and one core. A
cached grouped heatmap costs ~0.5 s of CPU, so the UI's parallel page-load requests
queued behind each other (4 concurrent heatmaps: up to 2.2 s with 1 process, up to 0.9 s
with 4).

Budget: `TK_API_WORKERS × (pool + overflow) + worker 30` must stay below Postgres
`max_connections` (default **100**, 3 reserved). Defaults give 4 × 10 + 30 = 70. If you
raise `TK_API_WORKERS`, lower the per-process pool or raise `max_connections`.

Running multiple processes is safe because all shared state lives in Postgres or Redis.
Caches are Redis-backed, scheduled jobs (finalize sweeper, stuck-job watchdog) run in the
arq worker, and `SessionMiddleware` commits before the response is sent, so a write is
visible to every process by the time the client sees a 2xx.

The image itself still defaults to **one** process (`WEB_CONCURRENCY` unset). Running it
outside these compose files keeps the old behaviour until you set both variables.

### Redis connection

| Variable | Default | Description |
|---|---|---|
| `TK_REDIS_URL` | — | Full Redis URL. If set, overrides all `TK_REDIS_*` vars below |
| `TK_REDIS_HOST` | `redis` | Redis host |
| `TK_REDIS_PORT` | `6379` | Redis port |
| `TK_REDIS_PASSWORD` | — | Redis password |

### Application

| Variable | Default | Description |
|---|---|---|
| `TK_SECRET_KEY` | — | Secret key for signing |
| `TK_CONFIG_PATH` | `config.yaml` | Path to the YAML config file |

### Prometheus adapter

| Variable | Default | Description |
|---|---|---|
| `PROMETHEUS_URL` | `http://prometheus:9090` | Prometheus server URL |
| `PROMETHEUS_USERNAME` | — | Basic auth username for Prometheus (optional; both halves required) |
| `PROMETHEUS_PASSWORD` | — | Basic auth password for Prometheus (optional; both halves required) |
| `ADAPTER_AUTH_TOKEN` | — | Shared secret required on the adapter's own query endpoints |

Prometheus itself authenticates incoming requests with basic auth or TLS client certificates only
— it has no bearer-token support — so basic auth is what the adapter implements. Managed services
that issue an "API token" generally expect it as the basic-auth *password*; set `PROMETHEUS_USERNAME`
to the account or instance id those services document. Setting only one of the pair logs a warning
and sends no credentials at all, rather than half a header.

`ADAPTER_AUTH_TOKEN` guards the adapter, not Prometheus. The query endpoints run caller-supplied
queries against live data, so anyone who can reach the adapter's port can read metrics while it is
unset — which is the default, and what the startup log warns about. Set it to the same value as the
`token` on the datasource registered for this adapter; TROPEK then presents it as
`Authorization: Bearer <token>`. `/health` stays open so container healthchecks keep working.

#### Serving more than one Prometheus

An adapter process targets exactly one Prometheus, fixed at startup. To evaluate against two
instances — separate labs, or separate monitored environments — run the adapter twice and register
each as its own datasource, pointing `adapter_url` at the matching container. Each service block is
its own env namespace, so both use the same container-side variable names while drawing different
values, and a credential leak is contained to one upstream:

```yaml
services:
  adapter-prometheus-lab:
    image: ghcr.io/domik82/tropek-adapter-prometheus:${TROPEK_VERSION:-latest}
    environment:
      PROMETHEUS_URL: ${PROM_LAB_URL}
      PROMETHEUS_USERNAME: ${PROM_LAB_USERNAME:-}
      PROMETHEUS_PASSWORD: ${PROM_LAB_PASSWORD:-}
      ADAPTER_AUTH_TOKEN: ${PROM_LAB_ADAPTER_TOKEN:-}
      REDIS_URL: redis://:${TK_REDIS_PASSWORD}@redis:6379/1

  adapter-prometheus-prod:
    image: ghcr.io/domik82/tropek-adapter-prometheus:${TROPEK_VERSION:-latest}
    environment:
      PROMETHEUS_URL: ${PROM_PROD_URL}
      PROMETHEUS_USERNAME: ${PROM_PROD_USERNAME:-}
      PROMETHEUS_PASSWORD: ${PROM_PROD_PASSWORD:-}
      ADAPTER_AUTH_TOKEN: ${PROM_PROD_ADAPTER_TOKEN:-}
      REDIS_URL: redis://:${TK_REDIS_PASSWORD}@redis:6379/2
```

Give each instance its own Redis database index, as above, so their job queues stay separate, and
its own `ADAPTER_AUTH_TOKEN` matching that datasource's `token` — sharing one secret across both
adapters means a leak from either reaches both upstreams. The `X-Datasource-Name` header the API
sends is recorded in the adapter's logs for correlation; it does not select an upstream.

## config.yaml Reference

```yaml
server:
  host: "0.0.0.0"
  port: 8080

database:
  host: "timescaledb"     # overridden by TK_DB_HOST
  port: 5432              # overridden by TK_DB_PORT
  name: "tropek"          # overridden by TK_DB_NAME
  pool_size: 10           # PER PROCESS — see "API processes and DB pool sizing" below
  max_overflow: 20

cache:
  backend: "redis"
  host: "redis"           # overridden by TK_REDIS_HOST
  port: 6379              # overridden by TK_REDIS_PORT
  db: 0
  ttl_seconds:
    trend: 60
    evaluation_list: 30
    evaluation_detail: 300
    slo_definition: 600
    heatmap_column: 604800  # 7 days

queue:
  db_index: 1
  max_jobs: 10
  max_retries: 3
  retry_delay_seconds: 10
  job_timeout_seconds: 120
  keep_result_seconds: 3600
  finalize_sweeper_interval_seconds: 30
  finalize_sweeper_batch_limit: 100

reliability:
  adapter_timeout_seconds: 30
  adapter_retry_attempts: 3
  adapter_retry_backoff_seconds: 2
  watchdog_interval_seconds: 60
  stuck_job_threshold_seconds: 180

evaluation:
  async_threshold_metrics: 10

adapters:
  prometheus:
    url: "http://adapter-prometheus:8080"
    timeout_seconds: 30
  max_concurrent_queries_per_adapter: 10

file_ingestion:
  allowed_path_prefix: "/data/results"
  max_file_size_mb: 50

ui:
  max_evaluations: 1000
  page_size: 200
  heatmap_slo_groups_expanded_by_default: true
  data_start_date: "2024-01-01"

logging:
  level: "INFO"
  format: "json"
```
