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
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


def _load_yaml() -> dict[str, Any]:
    path = Path(os.environ.get("QG_CONFIG_PATH", "config.yaml"))
    if not path.exists():
        return {}
    try:
        with path.open() as f:
            data = yaml.safe_load(f)
            if not isinstance(data, dict):
                logger.warning("config.yaml exists but parsed as non-dict, using defaults")
                return {}
            return data
    except yaml.YAMLError as exc:
        raise RuntimeError(f"config.yaml is malformed: {exc}") from exc


_yaml: dict[str, Any] = _load_yaml()


class DatabaseSettings(BaseSettings):
    """PostgreSQL / TimescaleDB connection settings.

    Credentials (user, password) are loaded from QG_DB_USER / QG_DB_PASSWORD env vars.
    """

    host: str = _yaml.get("database", {}).get("host", "localhost")
    port: int = _yaml.get("database", {}).get("port", 5432)
    name: str = _yaml.get("database", {}).get("name", "tropek")
    pool_size: int = _yaml.get("database", {}).get("pool_size", 10)
    max_overflow: int = _yaml.get("database", {}).get("max_overflow", 20)
    user: str = ""
    password: SecretStr = SecretStr("")

    model_config = SettingsConfigDict(env_prefix="QG_DB_")

    @property
    def async_url(self) -> str:
        """Construct the asyncpg connection URL from individual settings."""
        pw = self.password.get_secret_value()
        return f"postgresql+asyncpg://{self.user}:{pw}@{self.host}:{self.port}/{self.name}"


class CacheTTLSettings:
    """Per-endpoint cache TTL values in seconds."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.trend: int = data.get("trend", 60)
        self.evaluation_list: int = data.get("evaluation_list", 30)
        self.evaluation_detail: int = data.get("evaluation_detail", 300)
        self.slo_definition: int = data.get("slo_definition", 600)


class CacheSettings(BaseSettings):
    """Redis cache connection settings.

    Password is loaded from QG_REDIS_PASSWORD env var.
    """

    backend: str = _yaml.get("cache", {}).get("backend", "redis")
    host: str = _yaml.get("cache", {}).get("host", "redis")
    port: int = _yaml.get("cache", {}).get("port", 6379)
    db: int = _yaml.get("cache", {}).get("db", 0)
    password: SecretStr = SecretStr("")

    model_config = SettingsConfigDict(env_prefix="QG_REDIS_")

    @property
    def ttl(self) -> CacheTTLSettings:
        """Per-endpoint TTL configuration."""
        return CacheTTLSettings(_yaml.get("cache", {}).get("ttl_seconds", {}))

    @property
    def url(self) -> str:
        """Construct the Redis connection URL including auth if password is set."""
        pw = self.password.get_secret_value()
        auth = f":{pw}@" if pw else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"


class QueueSettings(BaseSettings):
    """arq job queue configuration (uses Redis db_index separate from cache)."""

    db_index: int = _yaml.get("queue", {}).get("db_index", 1)
    max_retries: int = _yaml.get("queue", {}).get("max_retries", 3)
    retry_delay_seconds: int = _yaml.get("queue", {}).get("retry_delay_seconds", 10)
    job_timeout_seconds: int = _yaml.get("queue", {}).get("job_timeout_seconds", 120)
    keep_result_seconds: int = _yaml.get("queue", {}).get("keep_result_seconds", 3600)


class ReliabilitySettings(BaseSettings):
    """Timeout, retry, and watchdog settings for evaluation job reliability."""

    adapter_timeout_seconds: int = _yaml.get("reliability", {}).get("adapter_timeout_seconds", 90)
    adapter_retry_attempts: int = _yaml.get("reliability", {}).get("adapter_retry_attempts", 3)
    adapter_retry_backoff_seconds: int = _yaml.get("reliability", {}).get(
        "adapter_retry_backoff_seconds", 2
    )
    watchdog_interval_seconds: int = _yaml.get("reliability", {}).get(
        "watchdog_interval_seconds", 60
    )
    stuck_job_threshold_seconds: int = _yaml.get("reliability", {}).get(
        "stuck_job_threshold_seconds", 180
    )


class AdapterInstanceSettings:
    """Connection settings for a single adapter service instance."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.url: str = data.get("url", "")
        self.timeout_seconds: int = data.get("timeout_seconds", 30)


class AdaptersSettings(BaseSettings):
    """Configuration for all registered data source adapters."""

    max_concurrent_queries_per_adapter: int = _yaml.get("adapters", {}).get(
        "max_concurrent_queries_per_adapter", 10
    )

    @property
    def prometheus(self) -> AdapterInstanceSettings:
        """Settings for the Prometheus adapter service."""
        return AdapterInstanceSettings(_yaml.get("adapters", {}).get("prometheus", {}))


class EvaluationSettings(BaseSettings):
    """Evaluation job behaviour settings."""

    async_threshold_metrics: int = _yaml.get("evaluation", {}).get("async_threshold_metrics", 10)


class UISettings(BaseSettings):
    """UI-facing limits served via GET /config/ui."""

    max_evaluations: int = _yaml.get("ui", {}).get("max_evaluations", 1000)
    page_size: int = _yaml.get("ui", {}).get("page_size", 200)


class FileIngestionSettings(BaseSettings):
    """File-mode ingestion security and size limits."""

    allowed_path_prefix: str = _yaml.get("file_ingestion", {}).get(
        "allowed_path_prefix", "/data/results"
    )
    max_file_size_mb: int = _yaml.get("file_ingestion", {}).get("max_file_size_mb", 50)


class Settings(BaseSettings):
    """Root settings object — access all config sections through properties.

    Secret key is loaded from QG_SECRET_KEY env var.
    """

    secret_key: SecretStr = SecretStr("")

    model_config = SettingsConfigDict(env_prefix="QG_")

    def validate_required(self) -> None:
        """Raise on missing required secrets. Call at startup."""
        missing = []
        if not self.database.password.get_secret_value():
            missing.append("QG_DB_PASSWORD")
        if not self.cache.password.get_secret_value():
            missing.append("QG_REDIS_PASSWORD")
        if not self.secret_key.get_secret_value():
            missing.append("QG_SECRET_KEY")
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
        return QueueSettings()

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
