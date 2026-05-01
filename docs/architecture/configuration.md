# Configuration

TROPEK uses a two-layer configuration system: `config.yaml` for non-secret settings
and `QG_*` environment variables for credentials.

## Loading Priority

```
HashiCorp Vault (highest priority)
  -> QG_* environment variables
    -> .env file
      -> config.yaml defaults (lowest priority)
```

All settings are loaded via Pydantic Settings (`pydantic-settings` library) into a
singleton cached with `@lru_cache`.

## Settings Classes

```mermaid
graph TD
    Settings["Settings (root)"]
    DB["DatabaseSettings"]
    Cache["CacheSettings"]
    TTL["CacheTTLSettings"]
    Queue["QueueSettings"]
    Rel["ReliabilitySettings"]
    Adapt["AdaptersSettings"]
    AdaptInst["AdapterInstanceSettings"]
    Eval["EvaluationSettings"]
    UI["UISettings"]
    File["FileIngestionSettings"]

    Settings --> DB
    Settings --> Cache
    Cache --> TTL
    Settings --> Queue
    Settings --> Rel
    Settings --> Adapt
    Adapt --> AdaptInst
    Settings --> Eval
    Settings --> UI
    Settings --> File
```

| Class | Env Prefix | Key Fields |
|-------|------------|------------|
| `DatabaseSettings` | `QG_DB_` | host, port, name, pool_size, max_overflow, user, password |
| `CacheSettings` | `QG_REDIS_` | backend, host, port, db, password |
| `CacheTTLSettings` | -- | trend (60s), evaluation_list (30s), evaluation_detail (300s), slo_definition (600s), heatmap_column (7 days) |
| `QueueSettings` | -- | db_index (1), max_jobs (10), max_retries (3), retry_delay_seconds (10), job_timeout_seconds (120), keep_result_seconds (3600), finalize_sweeper_interval_seconds (30), finalize_sweeper_batch_limit (100) |
| `ReliabilitySettings` | -- | adapter_timeout_seconds (90), adapter_retry_attempts (3), adapter_retry_backoff_seconds (2), watchdog_interval_seconds (60), stuck_job_threshold_seconds (180) |
| `AdaptersSettings` | -- | max_concurrent_queries_per_adapter (10) |
| `AdapterInstanceSettings` | -- | url, timeout_seconds (30) — one instance per named adapter (e.g. prometheus) |
| `EvaluationSettings` | -- | async_threshold_metrics (10) |
| `UISettings` | -- | max_evaluations (1000), page_size (200), heatmap_slo_groups_expanded_by_default (true), data_start_date |
| `FileIngestionSettings` | -- | allowed_path_prefix, max_file_size_mb (50) |

## Non-Secret Settings (config.yaml)

The `config.yaml` file is safe to commit. It contains:

- Server bind address and port
- Database connection pool tuning
- Redis cache TTLs per endpoint type
- Job queue retry and timeout policies
- Adapter URLs and concurrency limits
- Watchdog thresholds for stuck job detection
- File ingestion constraints
- Logging level and format

## Secret Settings (Environment Variables)

| Variable | Purpose |
|----------|---------|
| `QG_DB_USER` | PostgreSQL username |
| `QG_DB_PASSWORD` | PostgreSQL password |
| `QG_REDIS_PASSWORD` | Redis authentication |
| `QG_SECRET_KEY` | API secret key |
| `QG_CONFIG_PATH` | Path to config.yaml (default: `config.yaml`) |

## Environment Files

| File | Purpose |
|------|---------|
| `.env.example` | Template for production/dev secrets |
| `.env` | Active secrets (gitignored) |
| `.env.test.example` | Template for test database secrets |
| `.env.test` | Test DB secrets, loaded automatically by pytest-dotenv |
