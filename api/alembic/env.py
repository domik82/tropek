"""Alembic environment — async SQLAlchemy engine, URL from app config."""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from app.config import get_settings
from app.db.models import Base
from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

# Load the env file specified by ENV_FILE (default: .env).
# This lets `uv run alembic upgrade head` work without shell sourcing tricks —
# pass ENV_FILE=.env.test as a single env var prefix when targeting the test DB.
_env_file = Path(os.environ.get('ENV_FILE', '.env'))
load_dotenv(_env_file, override=False)  # env vars already in shell take precedence

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    """Return the async database URL from app settings."""
    return get_settings().database.async_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL without a live connection)."""
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={'paramstyle': 'named'},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    """Run migrations synchronously inside an async connection."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations."""
    cfg = config.get_section(config.config_ini_section, {})
    cfg['sqlalchemy.url'] = get_url()
    connectable = async_engine_from_config(
        cfg,
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online mode migrations."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
