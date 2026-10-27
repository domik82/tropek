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

ADAPTER_BUDGET_MARGIN_SECONDS = 30
ADAPTER_BUDGET_GRACE_SECONDS = 5  # the adapter's sync /query waits budget + this before answering 504
ADAPTER_MAX_JOB_TIMEOUT_SECONDS = 600  # the adapter's max_job_timeout_seconds; a larger budget is capped there
# Seconds of the job timeout kept free of adapter attempts, for evaluation, writes and change points.
JOB_TIMEOUT_MARGIN_SECONDS = 60


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
        self.trend_column: int = data.get('trend_column', 7 * 24 * 60 * 60)


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
    job_timeout_seconds: int = _yaml.get('queue', {}).get('job_timeout_seconds', 400)
    keep_result_seconds: int = _yaml.get('queue', {}).get('keep_result_seconds', 3600)
    finalize_sweeper_interval_seconds: int = _yaml.get('queue', {}).get('finalize_sweeper_interval_seconds', 30)
    finalize_sweeper_batch_limit: int = _yaml.get('queue', {}).get('finalize_sweeper_batch_limit', 100)

    @field_validator('max_retries')
    @classmethod
    def _validate_max_retries(cls, max_retries: int) -> int:
        if max_retries < 0:
            msg = f'max_retries must be >= 0, got {max_retries}'
            raise ValueError(msg)
        return max_retries

    @field_validator('finalize_sweeper_interval_seconds')
    @classmethod
    def _validate_sweeper_interval(cls, interval_seconds: int) -> int:
        allowed = {5, 10, 15, 20, 30, 60}
        if interval_seconds not in allowed:
            msg = (
                f'finalize_sweeper_interval_seconds must be one of {sorted(allowed)} (divisors of 60), '
                f'got {interval_seconds}'
            )
            raise ValueError(msg)
        return interval_seconds

    @field_validator('finalize_sweeper_batch_limit')
    @classmethod
    def _validate_sweeper_batch_limit(cls, batch_limit: int) -> int:
        if batch_limit < 1:
            msg = f'finalize_sweeper_batch_limit must be >= 1, got {batch_limit}'
            raise ValueError(msg)
        return batch_limit


_queue_settings: QueueSettings = QueueSettings()


class ReliabilitySettings(BaseSettings):
    """Timeout, retry, and watchdog settings for evaluation job reliability."""

    adapter_timeout_seconds: int = _yaml.get('reliability', {}).get('adapter_timeout_seconds', 330)
    adapter_retry_attempts: int = _yaml.get('reliability', {}).get('adapter_retry_attempts', 3)
    adapter_retry_backoff_seconds: int = _yaml.get('reliability', {}).get('adapter_retry_backoff_seconds', 2)
    watchdog_interval_seconds: int = _yaml.get('reliability', {}).get('watchdog_interval_seconds', 60)
    stuck_job_threshold_seconds: int = _yaml.get('reliability', {}).get('stuck_job_threshold_seconds', 600)
    max_stuck_job_retries: int = _yaml.get('reliability', {}).get('max_stuck_job_retries', 3)
    event_loop_lag_check_interval_seconds: float = _yaml.get('reliability', {}).get(
        'event_loop_lag_check_interval_seconds', 0.5
    )
    event_loop_lag_warn_threshold_seconds: float = _yaml.get('reliability', {}).get(
        'event_loop_lag_warn_threshold_seconds', 1.0
    )

    @field_validator('watchdog_interval_seconds')
    @classmethod
    def _validate_watchdog_interval(cls, interval_seconds: int) -> int:
        allowed = {5, 10, 15, 20, 30, 60}
        if interval_seconds not in allowed:
            msg = f'watchdog_interval_seconds must be one of {sorted(allowed)} (divisors of 60), got {interval_seconds}'
            raise ValueError(msg)
        return interval_seconds

    @field_validator('adapter_retry_attempts')
    @classmethod
    def _validate_adapter_retry_attempts(cls, attempts: int) -> int:
        if attempts < 1:
            msg = f'adapter_retry_attempts must be >= 1, got {attempts}'
            raise ValueError(msg)
        return attempts

    @field_validator('adapter_retry_backoff_seconds')
    @classmethod
    def _validate_adapter_retry_backoff_seconds(cls, backoff_seconds: int) -> int:
        if backoff_seconds < 0:
            msg = f'adapter_retry_backoff_seconds must be >= 0, got {backoff_seconds}'
            raise ValueError(msg)
        return backoff_seconds

    @field_validator('max_stuck_job_retries')
    @classmethod
    def _validate_max_stuck_job_retries(cls, max_stuck_job_retries: int) -> int:
        if max_stuck_job_retries < 1:
            msg = f'max_stuck_job_retries must be >= 1, got {max_stuck_job_retries}'
            raise ValueError(msg)
        return max_stuck_job_retries

    @property
    def adapter_budget_seconds(self) -> int:
        """Budget sent to the adapter as ``timeout_seconds``: the HTTP timeout minus a margin, floored."""
        return max(ADAPTER_BUDGET_MARGIN_SECONDS, self.adapter_timeout_seconds - ADAPTER_BUDGET_MARGIN_SECONDS)


def validate_timeout_chain(reliability: ReliabilitySettings, queue: QueueSettings) -> None:
    """Refuse a settings combination in which one hop gives up before the hop it waits on.

    The chain is: adapter budget + adapter grace < worker HTTP timeout, worker HTTP timeout + 60 s
    < job timeout (one attempt plus evaluation work), job timeout < stuck-job threshold.

    Args:
        reliability: Reliability settings (adapter HTTP timeout, stuck-job threshold).
        queue: Queue settings (job timeout).

    Raises:
        ValueError: If any hop of the chain is not larger than the hop it waits on.
    """
    adapter_timeout_floor = ADAPTER_BUDGET_MARGIN_SECONDS + ADAPTER_BUDGET_GRACE_SECONDS
    if reliability.adapter_timeout_seconds <= adapter_timeout_floor:
        msg = (
            f'reliability.adapter_timeout_seconds must exceed {adapter_timeout_floor} '
            f'(got {reliability.adapter_timeout_seconds})'
        )
        raise ValueError(msg)
    if reliability.adapter_budget_seconds > ADAPTER_MAX_JOB_TIMEOUT_SECONDS:
        msg = (
            f'adapter budget {reliability.adapter_budget_seconds} exceeds the adapter maximum '
            f'{ADAPTER_MAX_JOB_TIMEOUT_SECONDS}; lower reliability.adapter_timeout_seconds'
        )
        raise ValueError(msg)
    # Strict: at exactly +60 the client's deadline equals one attempt, so any elapsed time refuses every attempt.
    if queue.job_timeout_seconds <= reliability.adapter_timeout_seconds + JOB_TIMEOUT_MARGIN_SECONDS:
        msg = (
            f'queue.job_timeout_seconds must exceed adapter_timeout_seconds by more than {JOB_TIMEOUT_MARGIN_SECONDS} '
            f'(got {queue.job_timeout_seconds} and {reliability.adapter_timeout_seconds})'
        )
        raise ValueError(msg)
    if reliability.stuck_job_threshold_seconds <= queue.job_timeout_seconds:
        msg = (
            f'reliability.stuck_job_threshold_seconds must exceed job_timeout_seconds '
            f'({reliability.stuck_job_threshold_seconds} <= {queue.job_timeout_seconds})'
        )
        raise ValueError(msg)


class QualityGateInvalidateSettings(BaseSettings):
    """Deadlock retry settings for evaluation mutation actions (invalidate/restore/etc.)."""

    max_retries: int = _yaml.get('quality_gate', {}).get('invalidate', {}).get('max_retries', 5)
    base_backoff_ms: int = _yaml.get('quality_gate', {}).get('invalidate', {}).get('base_backoff_ms', 25)
    max_backoff_ms: int = _yaml.get('quality_gate', {}).get('invalidate', {}).get('max_backoff_ms', 500)

    @field_validator('max_retries')
    @classmethod
    def _validate_max_retries(cls, max_retries: int) -> int:
        if max_retries < 0:
            msg = f'max_retries must be >= 0, got {max_retries}'
            raise ValueError(msg)
        return max_retries

    @field_validator('base_backoff_ms', 'max_backoff_ms')
    @classmethod
    def _validate_backoff(cls, backoff_ms: int) -> int:
        if backoff_ms <= 0:
            msg = f'backoff milliseconds must be > 0, got {backoff_ms}'
            raise ValueError(msg)
        return backoff_ms


class QualityGateSettings(BaseSettings):
    """Quality gate behaviour settings."""

    @property
    def invalidate(self) -> QualityGateInvalidateSettings:
        """Deadlock retry settings for evaluation mutation actions."""
        return QualityGateInvalidateSettings()


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
    trend_prefetch_margin_px: int = _yaml.get('ui', {}).get('trend_prefetch_margin_px', 200)


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
        The worker timeout chain must be consistent (see ``validate_timeout_chain``).
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
        validate_timeout_chain(self.reliability, self.queue)

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
    def quality_gate(self) -> QualityGateSettings:
        """Quality gate behaviour settings."""
        return QualityGateSettings()

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
