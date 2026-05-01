"""Configuration repository — CRUD for the key-value settings table."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tropek.db.models import Configuration

VALID_TYPES = {'bool', 'int', 'float', 'str'}

TYPE_VALIDATORS: dict[str, Callable[[str], bool]] = {
    'bool': lambda v: v.lower() in ('true', 'false'),
    'int': lambda v: v.lstrip('-').isdigit(),
    'float': lambda v: _is_float(v),
    'str': lambda v: True,
}


def _is_float(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False


def parse_typed_value(value: str, value_type: str) -> bool | int | float | str:
    """Parse a string value into its typed Python equivalent."""
    match value_type:
        case 'bool':
            return value.lower() == 'true'
        case 'int':
            return int(value)
        case 'float':
            return float(value)
        case _:
            return value


class ConfigurationRepository:
    """Data access layer for system-wide configuration."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all(self, *, prefix: str | None = None) -> list[Configuration]:
        """Return all configuration entries, optionally filtered by key prefix."""
        query = select(Configuration).order_by(Configuration.name)
        if prefix:
            query = query.where(Configuration.name.startswith(prefix))
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def get_by_name(self, name: str) -> Configuration | None:
        """Return a single configuration entry by name."""
        result = await self._session.execute(
            select(Configuration).where(Configuration.name == name)
        )
        return result.scalar_one_or_none()

    async def update_value(self, name: str, value: str) -> Configuration | None:
        """Update the value of an existing configuration entry.

        Validates the value against the entry's value_type before updating.
        Returns None if the entry does not exist.
        """
        entry = await self.get_by_name(name)
        if entry is None:
            return None
        _accept_any: Callable[[str], bool] = lambda v: True
        validator = TYPE_VALIDATORS.get(entry.value_type, _accept_any)
        if not validator(value):
            msg = f"value '{value}' is not a valid {entry.value_type}"
            raise ValueError(msg)
        entry.value = value
        await self._session.flush()
        return entry

    async def get_change_point_defaults(self) -> dict[str, bool | int | float | str]:
        """Load all change_point.* settings as a typed dict."""
        rows = await self.get_all(prefix='change_point.')
        return {
            row.name.removeprefix('change_point.'): parse_typed_value(row.value, row.value_type)
            for row in rows
        }
