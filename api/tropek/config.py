"""Application configuration loaded from config.yaml with env-var overrides for secrets.

Non-secret settings are read from config.yaml (safe to commit).
Credentials (DB password, Redis password, secret key) come exclusively from
environment variables or Vault — never from the YAML file.

Loading priority (highest to lowest):
    Vault → Environment variables → .env file → config.yaml defaults
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


def _load_yaml() -> dict[str, Any]:
    path = Path(os.environ.get('TK_CONFIG_PATH', 'config.yaml'))
    if not path.exists():
        return {}
    try:
        with path.open() as f:
            data = yaml.safe_load(f)
            if not isinstance(data, dict):
                logger.warning('config.yaml exists but parsed as non-dict, using defaults')
                return {}
            return data
    except yaml.YAMLError as exc:
        raise RuntimeError(f'config.yaml is malformed: {exc}') from exc


_yaml: dict[str, Any] = _load_yaml()


class DatabaseSettings(BaseSettings):
    """PostgreSQL / TimescaleDB connection settings.

    Credentials (user, password) are loaded from TK_DB_USER / TK_DB_PASSWORD env vars.
    """

    host: str = _yaml.get('database', {}).get('host', 'localhost')
    port: int = _yaml.get('database', {}).get('port', 5432)
    name: str = _yaml.get('database', {}).get('name', 'tropek')
    pool_size: int = _yaml.get('database', {}).get('pool_size', 10)
    max_overflow: int = _yaml.get('database', {}).get('max_overflow', 20)
    user: str = ''
    password: SecretStr = SecretStr('')

    model_config = SettingsConfigDict(env_prefix='TK_DB_')

    @property
    def async_url(self) -> str:
        """Return the database URL, preferring TK_DATABASE_URL if set."""
        explicit_url = os.environ.get('TK_DATABASE_URL')
        if explicit_url:
            return explicit_url
        pw = self.password.get_secret_value()
        return f'postgresql+asyncpg://{self.user}:{pw}@{self.host}:{self.port}/{self.name}'


class CacheTTLSettings:
    """Per-endpoint cache TTL values in seconds."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.trend: int = data.get('trend', 60)
        self.evaluation_list: int = data.get('evaluation_list', 30)
        self.evaluation_detail: int = data.get('evaluation_detail', 300)
        self.slo_definition: int = data.get('slo_definition', 600)
        self.heatmap_column: int = data.get('heatmap_column', 7 * 24 * 60 * 60)


class CacheSettings(BaseSettings):
    """Redis cache connection settings.

    Password is loaded from TK_REDIS_PASSWORD env var.
    """

    backend: str = _yaml.get('cache', {}).get('backend', 'redis')
    host: str = _yaml.get('cache', {}).get('host', 'redis')
    port: int = _yaml.get('cache', {}).get('port', 6379)
    db: int = _yaml.get('cache', {}).get('db', 0)
    password: SecretStr = SecretStr('')

    model_config = SettingsConfigDict(env_prefix='TK_REDIS_')

    @property
    def ttl(self) -> CacheTTLSettings:
        """Per-endpoint TTL configuration."""
        return CacheTTLSettings(_yaml.get('cache', {}).get('ttl_seconds', {}))

    @property
    def url(self) -> str:
        """Return the Redis URL, preferring TK_REDIS_URL if set."""
        explicit_url = os.environ.get('TK_REDIS_URL')
        if explicit_url:
            return explicit_url
        pw = self.password.get_secret_value()
        auth = f':{pw}@' if pw else ''
        return f'redis://{auth}{self.host}:{self.port}/{self.db}'


class QueueSettings(BaseSettings):
    """arq job queue configuration (uses Redis db_index separate from cache)."""

    db_index: int = _yaml.get('queue', {}).get('db_index', 1)
    max_jobs: int = _yaml.get('queue', {}).get('max_jobs', 10)
    max_retries: int = _yaml.get('queue', {}).get('max_retries', 3)
    retry_delay_seconds: int = _yaml.get('queue', {}).get('retry_delay_seconds', 10)
    job_timeout_seconds: int = _yaml.get('queue', {}).get('job_timeout_seconds', 120)
    keep_result_seconds: int = _yaml.get('queue', {}).get('keep_result_seconds', 3600)
    finalize_sweeper_interval_seconds: int = _yaml.get('queue', {}).get('finalize_sweeper_interval_seconds', 30)
    finalize_sweeper_batch_limit: int = _yaml.get('queue', {}).get('finalize_sweeper_batch_limit', 100)

    @field_validator('finalize_sweeper_interval_seconds')
    @classmethod
    def _validate_sweeper_interval(cls, v: int) -> int:
        allowed = {5, 10, 15, 20, 30, 60}
        if v not in allowed:
            msg = f'finalize_sweeper_interval_seconds must be one of {sorted(allowed)} (divisors of 60), got {v}'
            raise ValueError(msg)
        return v

    @field_validator('finalize_sweeper_batch_limit')
    @classmethod
    def _validate_sweeper_batch_limit(cls, v: int) -> int:
        if v < 1:
            msg = f'finalize_sweeper_batch_limit must be >= 1, got {v}'
            raise ValueError(msg)
        return v


_queue_settings: QueueSettings = QueueSettings()


class ReliabilitySettings(BaseSettings):
    """Timeout, retry, and watchdog settings for evaluation job reliability."""

    adapter_timeout_seconds: int = _yaml.get('reliability', {}).get('adapter_timeout_seconds', 90)
    adapter_retry_attempts: int = _yaml.get('reliability', {}).get('adapter_retry_attempts', 3)
    adapter_retry_backoff_seconds: int = _yaml.get('reliability', {}).get('adapter_retry_backoff_seconds', 2)
    watchdog_interval_seconds: int = _yaml.get('reliability', {}).get('watchdog_interval_seconds', 60)
    stuck_job_threshold_seconds: int = _yaml.get('reliability', {}).get('stuck_job_threshold_seconds', 180)


class AdapterInstanceSettings:
    """Connection settings for a single adapter service instance."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.url: str = data.get('url', '')
        self.timeout_seconds: int = data.get('timeout_seconds', 30)


class AdaptersSettings(BaseSettings):
    """Configuration for all registered data source adapters."""

    max_concurrent_queries_per_adapter: int = _yaml.get('adapters', {}).get('max_concurrent_queries_per_adapter', 10)

    @property
    def prometheus(self) -> AdapterInstanceSettings:
        """Settings for the Prometheus adapter service."""
        return AdapterInstanceSettings(_yaml.get('adapters', {}).get('prometheus', {}))


class EvaluationSettings(BaseSettings):
    """Evaluation job behaviour settings."""

    async_threshold_metrics: int = _yaml.get('evaluation', {}).get('async_threshold_metrics', 10)


class UISettings(BaseSettings):
    """UI-facing limits served via GET /config/ui."""

    max_evaluations: int = _yaml.get('ui', {}).get('max_evaluations', 1000)
    page_size: int = _yaml.get('ui', {}).get('page_size', 200)
    heatmap_slo_groups_expanded_by_default: bool = _yaml.get('ui', {}).get(
        'heatmap_slo_groups_expanded_by_default', True
    )
    data_start_date: str = _yaml.get('ui', {}).get('data_start_date', '2024-01-01')


class FileIngestionSettings(BaseSettings):
    """File-mode ingestion security and size limits."""

    allowed_path_prefix: str = _yaml.get('file_ingestion', {}).get('allowed_path_prefix', '/data/results')
    max_file_size_mb: int = _yaml.get('file_ingestion', {}).get('max_file_size_mb', 50)


class Settings(BaseSettings):
    """Root settings object — access all config sections through properties.

    Secret key is loaded from TK_SECRET_KEY env var.
    """

    secret_key: SecretStr = SecretStr('')

    model_config = SettingsConfigDict(env_prefix='TK_')

    def validate_required(self) -> None:
        """Raise on missing required secrets. Call at startup.

        Either TK_DATABASE_URL or TK_DB_PASSWORD must be set.
        Either TK_REDIS_URL or TK_REDIS_PASSWORD must be set.
        TK_SECRET_KEY is always required.
        """
        missing = []
        if not os.environ.get('TK_DATABASE_URL') and not self.database.password.get_secret_value():
            missing.append('TK_DB_PASSWORD (or TK_DATABASE_URL)')
        if not os.environ.get('TK_REDIS_URL') and not self.cache.password.get_secret_value():
            missing.append('TK_REDIS_PASSWORD (or TK_REDIS_URL)')
        if not self.secret_key.get_secret_value():
            missing.append('TK_SECRET_KEY')
        if missing:
            raise RuntimeError(f'required secrets not set: {", ".join(missing)}')

    @property
    def database(self) -> DatabaseSettings:
        """Database connection settings."""
        return DatabaseSettings()

    @property
    def cache(self) -> CacheSettings:
        """Redis cache settings."""
        return CacheSettings()

    @property
    def queue(self) -> QueueSettings:
        """Job queue settings."""
        return _queue_settings

    @property
    def reliability(self) -> ReliabilitySettings:
        """Reliability and retry settings."""
        return ReliabilitySettings()

    @property
    def adapters(self) -> AdaptersSettings:
        """Adapter service settings."""
        return AdaptersSettings()

    @property
    def evaluation(self) -> EvaluationSettings:
        """Evaluation job behaviour settings."""
        return EvaluationSettings()

    @property
    def ui(self) -> UISettings:
        """UI-facing configuration."""
        return UISettings()

    @property
    def file_ingestion(self) -> FileIngestionSettings:
        """File ingestion security settings."""
        return FileIngestionSettings()


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings singleton."""
    return Settings()
