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
| `TK_ADAPTER_PROMETHEUS_USERNAME` | — | Basic auth username (optional) |
| `TK_ADAPTER_PROMETHEUS_PASSWORD` | — | Basic auth password (optional) |

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
