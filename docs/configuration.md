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
| `PROMETHEUS_USERNAME` | — | Basic auth username (optional; both halves required) |
| `PROMETHEUS_PASSWORD` | — | Basic auth password (optional; both halves required) |

Prometheus itself authenticates incoming requests with basic auth or TLS client certificates only
— it has no bearer-token support — so basic auth is what the adapter implements. Managed services
that issue an "API token" generally expect it as the basic-auth *password*; set `PROMETHEUS_USERNAME`
to the account or instance id those services document. Setting only one of the pair logs a warning
and sends no credentials at all, rather than half a header.

#### Serving more than one Prometheus

An adapter process targets exactly one Prometheus, fixed at startup. To evaluate against two
instances — separate labs, or separate monitored environments — run the adapter twice and register each as
its own datasource, pointing `adapter_url` at the matching container. Each service block is its own
env namespace, so both use the same container-side variable names while drawing different values,
and a credential leak is contained to one upstream:

```yaml
services:
  adapter-prometheus-lab:
    image: ghcr.io/domik82/tropek-adapter-prometheus:${TROPEK_VERSION:-latest}
    environment:
      PROMETHEUS_URL: ${PROM_LAB_URL}
      PROMETHEUS_USERNAME: ${PROM_LAB_USERNAME:-}
      PROMETHEUS_PASSWORD: ${PROM_LAB_PASSWORD:-}
      REDIS_URL: redis://:${TK_REDIS_PASSWORD}@redis:6379/1

  adapter-prometheus-prod:
    image: ghcr.io/domik82/tropek-adapter-prometheus:${TROPEK_VERSION:-latest}
    environment:
      PROMETHEUS_URL: ${PROM_PROD_URL}
      PROMETHEUS_USERNAME: ${PROM_PROD_USERNAME:-}
      PROMETHEUS_PASSWORD: ${PROM_PROD_PASSWORD:-}
      REDIS_URL: redis://:${TK_REDIS_PASSWORD}@redis:6379/2
```

Give each instance its own Redis database index, as above, so their job queues stay separate. The
`X-Datasource-Name` header the API sends is recorded in the adapter's logs for correlation; it does
not select an upstream.

## config.yaml Reference

```yaml
server:
  host: "0.0.0.0"
  port: 8080

database:
  host: "timescaledb"     # overridden by TK_DB_HOST
  port: 5432              # overridden by TK_DB_PORT
  name: "tropek"          # overridden by TK_DB_NAME
  pool_size: 10
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
