"""Tests for adapter configuration defaults and env-var overrides."""

import logging
from pathlib import Path

import pytest
import yaml
from tropek_prometheus.config import Settings, resolve_basic_auth

_REPO_ROOT = Path(__file__).parents[3]
_COMPOSE_FILES = ('docker-compose.yml', 'deploy/docker-compose.yml')


@pytest.fixture
def no_ambient_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear every env var that binds to a ``Settings`` field.

    ``pytest-dotenv`` loads the repo-root ``.env`` into ``os.environ`` for every run, so a
    developer who has one would otherwise see their own deployment values asserted as defaults.
    """
    for field in Settings.model_fields:
        monkeypatch.delenv(field.upper(), raising=False)


def test_default_settings(no_ambient_env: None):
    s = Settings()
    assert s.port == 8080
    assert s.prometheus_url == 'http://localhost:9090'
    assert s.redis_url == 'redis://localhost:6379/0'
    assert s.redis_key_prefix == 'prom-sli:'
    assert s.max_concurrent_queries == 10
    assert s.max_concurrent_jobs == 3
    assert s.max_queue_depth == 100
    assert s.max_queries_per_job == 400
    assert s.default_job_timeout_seconds == 120
    assert s.max_job_timeout_seconds == 600
    assert s.query_timeout_seconds == 30
    assert s.job_retention_seconds == 3600
    assert s.default_chunk_size == '4h'
    assert s.default_parallel_chunks == 3
    assert s.log_level == 'INFO'


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv('MAX_CONCURRENT_QUERIES', '20')
    monkeypatch.setenv('PROMETHEUS_URL', 'http://prom:9090')
    s = Settings()
    assert s.max_concurrent_queries == 20
    assert s.prometheus_url == 'http://prom:9090'


@pytest.mark.parametrize('compose_file', _COMPOSE_FILES)
def test_compose_only_sets_env_vars_the_adapter_reads(compose_file: str) -> None:
    """Every env var the shipped compose passes must be one ``Settings`` actually binds.

    ``Settings`` declares no ``env_prefix``, so each field binds to its own name. A compose key
    that matches no field is silently ignored — which is how the basic-auth credentials came to be
    passed under a name nothing read, leaving an authenticated Prometheus failing with the
    credentials plainly set in ``.env``.
    """
    compose = yaml.safe_load((_REPO_ROOT / compose_file).read_text())
    environment = compose['services']['adapter-prometheus']['environment']
    known = {name.upper() for name in Settings.model_fields}
    unreadable = sorted(key for key in environment if key.upper() not in known)
    assert not unreadable, (
        f'{compose_file} passes env vars to adapter-prometheus that Settings never reads: '
        f'{unreadable}. Either rename them to a Settings field or drop them.'
    )


def test_basic_auth_read_from_documented_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """The documented names must be the ones that populate the credential fields."""
    monkeypatch.setenv('PROMETHEUS_USERNAME', 'scraper')
    monkeypatch.setenv('PROMETHEUS_PASSWORD', 'secret')
    settings = Settings()
    assert settings.prometheus_username == 'scraper'
    assert settings.prometheus_password == 'secret'
    assert resolve_basic_auth(settings) == ('scraper', 'secret')


def test_no_basic_auth_when_neither_credential_is_set() -> None:
    """Prometheus without authentication stays the default, with no warning."""
    assert resolve_basic_auth(Settings(prometheus_username=None, prometheus_password=None)) is None


@pytest.mark.parametrize(
    ('username', 'password'),
    [('scraper', None), (None, 'secret')],
)
def test_half_configured_credentials_warn(
    username: str | None,
    password: str | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Half a credential is always an operator mistake; it must not pass silently.

    The adapter still starts, matching how an unreachable Prometheus is handled, but the log says
    plainly that requests will be unauthenticated.
    """
    settings = Settings(prometheus_username=username, prometheus_password=password)
    with caplog.at_level(logging.WARNING):
        assert resolve_basic_auth(settings) is None
    assert 'PROMETHEUS_USERNAME' in caplog.text
    assert 'PROMETHEUS_PASSWORD' in caplog.text
