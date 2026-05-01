from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest
import tropek.config as config_module


@pytest.fixture(autouse=True)
def _isolate_env():
    """Save TK_* env vars, clear them before each test, restore after.

    pytest-dotenv loads .env.test which sets TK_DB_HOST, TK_DB_PORT, etc.
    These pydantic-settings env vars override YAML defaults, breaking tests
    that expect YAML values to take effect. This fixture ensures a clean env.
    """
    saved = {k: v for k, v in os.environ.items() if k.startswith('TK_')}
    for k in saved:
        del os.environ[k]
    yield
    # Restore originals and clean up any test-set vars
    for k in list(os.environ):
        if k.startswith('TK_'):
            del os.environ[k]
    os.environ.update(saved)

    config_module.get_settings.cache_clear()


def test_config_loads_from_yaml(tmp_path: Path) -> None:
    cfg_file = tmp_path / 'config.yaml'
    cfg_file.write_text('database:\n  host: myhost\n  port: 5432\n  name: testdb\n')

    os.environ['TK_CONFIG_PATH'] = str(cfg_file)
    os.environ['TK_DB_USER'] = 'testuser'
    os.environ['TK_DB_PASSWORD'] = 'testpass'
    os.environ['TK_REDIS_PASSWORD'] = 'redispass'
    os.environ['TK_SECRET_KEY'] = 'testsecret'

    importlib.reload(config_module)

    settings = config_module.get_settings()
    assert settings.database.host == 'myhost'
    assert settings.database.name == 'testdb'
    assert settings.database.user == 'testuser'
    assert settings.database.password.get_secret_value() == 'testpass'


def test_env_overrides_yaml(tmp_path: Path) -> None:
    cfg_file = tmp_path / 'config.yaml'
    cfg_file.write_text('database:\n  host: localhost\n  port: 5432\n  name: tropek\n')

    os.environ['TK_CONFIG_PATH'] = str(cfg_file)
    os.environ['TK_DB_USER'] = 'override_user'
    os.environ['TK_DB_PASSWORD'] = 'pass'
    os.environ['TK_REDIS_PASSWORD'] = 'rpass'
    os.environ['TK_SECRET_KEY'] = 'secret'

    importlib.reload(config_module)

    settings = config_module.get_settings()
    assert settings.database.user == 'override_user'


def test_async_db_url_format(tmp_path: Path) -> None:
    cfg_file = tmp_path / 'config.yaml'
    cfg_file.write_text('database:\n  host: mydb\n  port: 5432\n  name: tropek\n')

    os.environ['TK_CONFIG_PATH'] = str(cfg_file)
    os.environ['TK_DB_USER'] = 'user'
    os.environ['TK_DB_PASSWORD'] = 'secret'
    os.environ['TK_REDIS_PASSWORD'] = 'r'
    os.environ['TK_SECRET_KEY'] = 's'

    importlib.reload(config_module)

    url = config_module.get_settings().database.async_url
    assert url.startswith('postgresql+asyncpg://')
    assert 'mydb' in url
    assert 'tropek' in url


def test_cache_url_includes_password(tmp_path: Path) -> None:
    cfg_file = tmp_path / 'config.yaml'
    cfg_file.write_text('cache:\n  host: myredis\n  port: 6379\n  db: 0\n')

    os.environ['TK_CONFIG_PATH'] = str(cfg_file)
    os.environ['TK_DB_USER'] = 'u'
    os.environ['TK_DB_PASSWORD'] = 'p'
    os.environ['TK_REDIS_PASSWORD'] = 'myredispass'
    os.environ['TK_SECRET_KEY'] = 's'

    importlib.reload(config_module)

    url = config_module.get_settings().cache.url
    assert 'myredispass' in url
    assert 'myredis' in url


def test_missing_config_file_uses_defaults(tmp_path: Path) -> None:
    os.environ['TK_CONFIG_PATH'] = str(tmp_path / 'nonexistent.yaml')
    os.environ['TK_DB_USER'] = 'u'
    os.environ['TK_DB_PASSWORD'] = 'p'
    os.environ['TK_REDIS_PASSWORD'] = 'r'
    os.environ['TK_SECRET_KEY'] = 's'

    importlib.reload(config_module)

    settings = config_module.get_settings()
    assert settings.database.host == 'localhost'
    assert settings.queue.job_timeout_seconds == 120


def test_queue_sweeper_defaults(tmp_path: Path) -> None:
    """Sweeper config has sane defaults when not present in YAML."""
    cfg_file = tmp_path / 'config.yaml'
    cfg_file.write_text('database:\n  host: h\n  port: 5432\n  name: n\n')

    os.environ['TK_CONFIG_PATH'] = str(cfg_file)
    os.environ['TK_DB_USER'] = 'u'
    os.environ['TK_DB_PASSWORD'] = 'p'
    os.environ['TK_REDIS_PASSWORD'] = 'r'
    os.environ['TK_SECRET_KEY'] = 's'

    importlib.reload(config_module)
    settings = config_module.get_settings()

    assert settings.queue.finalize_sweeper_interval_seconds == 30
    assert settings.queue.finalize_sweeper_batch_limit == 100


def test_queue_sweeper_accepts_valid_interval(tmp_path: Path) -> None:
    """Interval=5 (a divisor of 60) is accepted."""
    cfg_file = tmp_path / 'config.yaml'
    cfg_file.write_text(
        'database:\n  host: h\n  port: 5432\n  name: n\nqueue:\n  finalize_sweeper_interval_seconds: 5\n'
    )
    os.environ['TK_CONFIG_PATH'] = str(cfg_file)
    os.environ['TK_DB_USER'] = 'u'
    os.environ['TK_DB_PASSWORD'] = 'p'
    os.environ['TK_REDIS_PASSWORD'] = 'r'
    os.environ['TK_SECRET_KEY'] = 's'

    importlib.reload(config_module)
    settings = config_module.get_settings()

    assert settings.queue.finalize_sweeper_interval_seconds == 5


def test_queue_sweeper_rejects_invalid_interval(tmp_path: Path) -> None:
    """Interval=45 (not a divisor of 60) raises at settings construction."""
    cfg_file = tmp_path / 'config.yaml'
    cfg_file.write_text(
        'database:\n  host: h\n  port: 5432\n  name: n\nqueue:\n  finalize_sweeper_interval_seconds: 45\n'
    )
    os.environ['TK_CONFIG_PATH'] = str(cfg_file)
    os.environ['TK_DB_USER'] = 'u'
    os.environ['TK_DB_PASSWORD'] = 'p'
    os.environ['TK_REDIS_PASSWORD'] = 'r'
    os.environ['TK_SECRET_KEY'] = 's'

    with pytest.raises(ValueError, match='finalize_sweeper_interval_seconds'):
        importlib.reload(config_module)


def test_queue_sweeper_rejects_zero_batch_limit(tmp_path: Path) -> None:
    """batch_limit=0 raises."""
    cfg_file = tmp_path / 'config.yaml'
    cfg_file.write_text('database:\n  host: h\n  port: 5432\n  name: n\nqueue:\n  finalize_sweeper_batch_limit: 0\n')
    os.environ['TK_CONFIG_PATH'] = str(cfg_file)
    os.environ['TK_DB_USER'] = 'u'
    os.environ['TK_DB_PASSWORD'] = 'p'
    os.environ['TK_REDIS_PASSWORD'] = 'r'
    os.environ['TK_SECRET_KEY'] = 's'

    with pytest.raises(ValueError, match='finalize_sweeper_batch_limit'):
        importlib.reload(config_module)
