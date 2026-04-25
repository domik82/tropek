"""Configuration API — system-wide key-value settings."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from tropek.db.session import get_session
from tropek.modules.configuration.repository import ConfigurationRepository
from tropek.modules.configuration.schemas import ConfigurationRead, ConfigurationUpdate

router = APIRouter(tags=['configuration'])


@router.get('/configuration', response_model=list[ConfigurationRead])
async def list_configuration(
    prefix: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[ConfigurationRead]:
    """List all configuration entries, optionally filtered by key prefix."""
    repo = ConfigurationRepository(session)
    rows = await repo.get_all(prefix=prefix)
    return [ConfigurationRead.model_validate(row) for row in rows]


@router.get('/configuration/{name:path}', response_model=ConfigurationRead)
async def get_configuration(
    name: str,
    session: AsyncSession = Depends(get_session),
) -> ConfigurationRead:
    """Get a single configuration entry by name."""
    repo = ConfigurationRepository(session)
    entry = await repo.get_by_name(name)
    if entry is None:
        raise HTTPException(status_code=404, detail='configuration entry not found')
    return ConfigurationRead.model_validate(entry)


@router.put('/configuration/{name:path}', response_model=ConfigurationRead)
async def update_configuration(
    name: str,
    body: ConfigurationUpdate,
    session: AsyncSession = Depends(get_session),
) -> ConfigurationRead:
    """Update a configuration value. The entry must already exist (seeded by migration)."""
    repo = ConfigurationRepository(session)
    try:
        entry = await repo.update_value(name, body.value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if entry is None:
        raise HTTPException(status_code=404, detail='configuration entry not found')
    await session.commit()
    return ConfigurationRead.model_validate(entry)
