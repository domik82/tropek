from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def clear_lru_cache():
    """Clear the settings cache before each test."""
    yield
    import app.config as config_module

    config_module.get_settings.cache_clear()


def test_config_loads_from_yaml(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("database:\n  host: myhost\n  port: 5432\n  name: testdb\n")

    os.environ["QG_CONFIG_PATH"] = str(cfg_file)
    os.environ["QG_DB_USER"] = "testuser"
    os.environ["QG_DB_PASSWORD"] = "testpass"
    os.environ["QG_REDIS_PASSWORD"] = "redispass"
    os.environ["QG_SECRET_KEY"] = "testsecret"

    import app.config as config_module

    importlib.reload(config_module)

    settings = config_module.get_settings()
    assert settings.database.host == "myhost"
    assert settings.database.name == "testdb"
    assert settings.database.user == "testuser"
    assert settings.database.password.get_secret_value() == "testpass"


def test_env_overrides_yaml(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("database:\n  host: localhost\n  port: 5432\n  name: tropek\n")

    os.environ["QG_CONFIG_PATH"] = str(cfg_file)
    os.environ["QG_DB_USER"] = "override_user"
    os.environ["QG_DB_PASSWORD"] = "pass"
    os.environ["QG_REDIS_PASSWORD"] = "rpass"
    os.environ["QG_SECRET_KEY"] = "secret"

    import app.config as config_module

    importlib.reload(config_module)

    settings = config_module.get_settings()
    assert settings.database.user == "override_user"


def test_async_db_url_format(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("database:\n  host: mydb\n  port: 5432\n  name: tropek\n")

    os.environ["QG_CONFIG_PATH"] = str(cfg_file)
    os.environ["QG_DB_USER"] = "user"
    os.environ["QG_DB_PASSWORD"] = "secret"
    os.environ["QG_REDIS_PASSWORD"] = "r"
    os.environ["QG_SECRET_KEY"] = "s"

    import app.config as config_module

    importlib.reload(config_module)

    url = config_module.get_settings().database.async_url
    assert url.startswith("postgresql+asyncpg://")
    assert "mydb" in url
    assert "tropek" in url


def test_cache_url_includes_password(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("cache:\n  host: myredis\n  port: 6379\n  db: 0\n")

    os.environ["QG_CONFIG_PATH"] = str(cfg_file)
    os.environ["QG_DB_USER"] = "u"
    os.environ["QG_DB_PASSWORD"] = "p"
    os.environ["QG_REDIS_PASSWORD"] = "myredispass"
    os.environ["QG_SECRET_KEY"] = "s"

    import app.config as config_module

    importlib.reload(config_module)

    url = config_module.get_settings().cache.url
    assert "myredispass" in url
    assert "myredis" in url


def test_missing_config_file_uses_defaults(tmp_path: Path) -> None:
    os.environ["QG_CONFIG_PATH"] = str(tmp_path / "nonexistent.yaml")
    os.environ["QG_DB_USER"] = "u"
    os.environ["QG_DB_PASSWORD"] = "p"
    os.environ["QG_REDIS_PASSWORD"] = "r"
    os.environ["QG_SECRET_KEY"] = "s"

    import app.config as config_module

    importlib.reload(config_module)

    settings = config_module.get_settings()
    assert settings.database.host == "localhost"
    assert settings.queue.job_timeout_seconds == 120
