"""Mixin for JSONB tag key/value queries shared across repositories."""

from __future__ import annotations

from typing import Any, ClassVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import MappedColumn


class TagQueryMixin:
    """Provides get_tag_keys() and get_tag_values() for any table with a JSONB `tags` column.

    Subclasses must set `_tag_model` to an ORM class with a JSONB ``tags`` column
    and have a ``_session`` attribute.
    """

    _tag_model: ClassVar[type]
    _session: AsyncSession

    def _tags_col(self) -> MappedColumn[dict[str, Any]]:
        col: MappedColumn[dict[str, Any]] = self._tag_model.tags  # type: ignore[attr-defined]
        return col

    async def get_tag_keys(self) -> dict[str, int]:
        """Return all distinct tag keys with count of records using each."""
        tags = self._tags_col()
        key_col = func.jsonb_object_keys(tags).label('key')
        subq = select(key_col).subquery()
        stmt = (
            select(subq.c.key, func.count())
            .group_by(subq.c.key)
            .order_by(func.count().desc())
        )
        result = await self._session.execute(stmt)
        return {row[0]: row[1] for row in result}

    async def get_tag_values(self, key: str) -> dict[str, int]:
        """Return all distinct values for a tag key with usage counts."""
        tags = self._tags_col()
        val = tags[key].astext.label('val')
        stmt = (
            select(val, func.count())
            .where(tags.has_key(key))  # type: ignore[attr-defined]
            .group_by(val)
            .order_by(func.count().desc())
        )
        result = await self._session.execute(stmt)
        return {row[0]: row[1] for row in result}
