"""Adapter configuration from environment variables."""

import logging

from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


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


def resolve_basic_auth(settings: Settings) -> tuple[str, str] | None:
    """Return the Prometheus basic-auth pair, or ``None`` to query without credentials.

    Both halves are required. Exactly one is always an operator mistake rather than an intent, so
    it is logged loudly instead of silently downgrading to unauthenticated requests — the adapter
    still starts, matching how an unreachable Prometheus is handled.

    :param Settings settings: Adapter settings holding the configured credentials.
    :returns: ``(username, password)`` when both are set, otherwise ``None``.
    :rtype: tuple[str, str] | None
    """
    username = settings.prometheus_username
    password = settings.prometheus_password
    if username and password:
        return username, password
    if username or password:
        missing = 'PROMETHEUS_PASSWORD' if username else 'PROMETHEUS_USERNAME'
        present = 'PROMETHEUS_USERNAME' if username else 'PROMETHEUS_PASSWORD'
        logger.warning(
            'only %s is set (%s is empty) — basic auth needs both, so requests to prometheus '
            'will be sent WITHOUT credentials',
            present,
            missing,
        )
    return None
