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


@pytest.mark.parametrize(
    ('overrides', 'field'),
    [
        ({'default_job_timeout_seconds': 601}, 'default_job_timeout_seconds'),
        ({'max_concurrent_prometheus_requests': 0}, 'max_concurrent_prometheus_requests'),
        ({'prometheus_retry_attempts': 0}, 'prometheus_retry_attempts'),
        ({'max_concurrent_jobs': 0}, 'max_concurrent_jobs'),
        ({'max_concurrent_queries': 0}, 'max_concurrent_queries'),
    ],
)
def test_invalid_limits_are_rejected(overrides: dict[str, int], field: str) -> None:
    with pytest.raises(ValueError, match=field):
        Settings(**overrides)


def test_default_timeout_equal_to_max_is_accepted() -> None:
    settings = Settings(default_job_timeout_seconds=600, max_job_timeout_seconds=600)
    assert settings.default_job_timeout_seconds == 600
