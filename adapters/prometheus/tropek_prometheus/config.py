"""Adapter configuration from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All settings have safe defaults. Override via env vars."""

    port: int = 8080
    prometheus_url: str = 'http://localhost:9090'
    prometheus_username: str | None = None
    prometheus_password: str | None = None

    redis_url: str = 'redis://localhost:6379/0'
    redis_key_prefix: str = 'prom-sli:'

    max_concurrent_queries: int = 10
    max_concurrent_jobs: int = 3
    max_queue_depth: int = 100
    max_queries_per_job: int = 400

    default_job_timeout_seconds: int = 120
    max_job_timeout_seconds: int = 600
    query_timeout_seconds: int = 30
    job_retention_seconds: int = 3600

    default_chunk_size: str = '4h'
    default_parallel_chunks: int = 3

    log_level: str = 'INFO'
    log_dir: str | None = None
