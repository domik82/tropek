"""Mixin for JSONB tag key/value queries shared across repositories."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class TagQueryMixin:
    """Provides get_tag_keys() and get_tag_values() for any table with a JSONB `tags` column.

    Subclasses must set `_tag_table` to the SQL table name and have a `_session` attribute.
    """

    _tag_table: str
    _session: AsyncSession

    async def get_tag_keys(self) -> dict[str, int]:
        """Return all distinct tag keys with count of records using each."""
        result = await self._session.execute(
            text(
                f'SELECT key, COUNT(*) as cnt '  # noqa: S608
                f'FROM {self._tag_table}, jsonb_object_keys(tags) AS key '
                f'GROUP BY key ORDER BY cnt DESC'
            )
        )
        return {row[0]: row[1] for row in result}

    async def get_tag_values(self, key: str) -> dict[str, int]:
        """Return all distinct values for a tag key with usage counts."""
        result = await self._session.execute(
            text(
                f'SELECT tags->>:key AS val, COUNT(*) as cnt '  # noqa: S608
                f'FROM {self._tag_table} '
                f'WHERE tags ? :key '
                f'GROUP BY val ORDER BY cnt DESC'
            ),
            {'key': key},
        )
        return {row[0]: row[1] for row in result}
