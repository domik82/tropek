"""DataSource repository — CRUD for data_sources table."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DataSource


class DataSourceRepository:
    """Data access layer for datasource registrations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        name: str,
        adapter_type: str,
        adapter_url: str,
        display_name: str | None = None,
        tags: dict[str, Any] | None = None,
        token: str | None = None,
    ) -> DataSource:
        """Register a new datasource.

        Args:
            name: Unique name for this datasource registration.
            adapter_type: The adapter kind (e.g. "prometheus").
            adapter_url: Base URL of the running adapter service.
            display_name: Optional human-readable label.
            tags: Optional free-form metadata tags.
            token: Optional authentication token for the adapter.

        Returns:
            The newly created DataSource record.
        """
        ds = DataSource(
            id=uuid.uuid4(),
            name=name,
            display_name=display_name,
            adapter_type=adapter_type,
            adapter_url=adapter_url,
            tags=tags or {},
            token=token,
        )
        self._session.add(ds)
        await self._session.flush()
        return ds

    async def get_by_name(self, name: str) -> DataSource | None:
        """Return datasource by unique name, or None.

        Args:
            name: Unique datasource name.

        Returns:
            Matching DataSource, or None.
        """
        result = await self._session.execute(select(DataSource).where(DataSource.name == name))
        return result.scalar_one_or_none()

    async def list_all(
        self,
        *,
        adapter_type: str | None = None,
        tag_key: str | None = None,
        tag_val: str | None = None,
    ) -> list[DataSource]:
        """Return all registered datasources, optionally filtered.

        Args:
            adapter_type: When given, only return datasources of this adapter kind.
            tag_key: Tag key to filter by (requires tag_val).
            tag_val: Tag value to filter by (requires tag_key).

        Returns:
            Matching DataSource records ordered by name.
        """
        q = select(DataSource).order_by(DataSource.name)
        if adapter_type:
            q = q.where(DataSource.adapter_type == adapter_type)
        if tag_key and tag_val:
            q = q.where(DataSource.tags[tag_key].as_string() == tag_val)
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def update(
        self,
        name: str,
        *,
        display_name: str | None = None,
        adapter_url: str | None = None,
        tags: dict[str, Any] | None = None,
        token: str | None = None,
    ) -> DataSource | None:
        """Update mutable fields on an existing DataSource. Returns None if not found.

        Args:
            name: Unique datasource name to update.
            display_name: New human-readable label, if changing.
            adapter_url: New adapter base URL, if changing.
            tags: New tags dict, if changing.
            token: New authentication token, if changing.

        Returns:
            Updated DataSource, or None if not found.
        """
        values: dict[str, Any] = {}
        if display_name is not None:
            values["display_name"] = display_name
        if adapter_url is not None:
            values["adapter_url"] = adapter_url
        if tags is not None:
            values["tags"] = tags
        if token is not None:
            values["token"] = token
        if values:
            await self._session.execute(
                update(DataSource).where(DataSource.name == name).values(**values)
            )
        return await self.get_by_name(name)

    async def delete(self, datasource_id: uuid.UUID) -> None:
        """Hard-delete a datasource record.

        Args:
            datasource_id: UUID of the datasource to remove.
        """
        await self._session.execute(delete(DataSource).where(DataSource.id == datasource_id))

    async def delete_by_name(self, name: str) -> bool:
        """Delete a datasource by name. Returns False if not found.

        Args:
            name: Unique datasource name to delete.

        Returns:
            True if deleted, False if not found.
        """
        ds = await self.get_by_name(name)
        if ds is None:
            return False
        await self._session.execute(delete(DataSource).where(DataSource.id == ds.id))
        return True

    async def get_tag_keys(self) -> dict[str, int]:
        """Return all distinct tag keys with count of datasources using each."""
        result = await self._session.execute(
            text(
                "SELECT key, COUNT(*) as cnt "
                "FROM data_sources, jsonb_object_keys(tags) AS key "
                "GROUP BY key ORDER BY cnt DESC"
            )
        )
        return {row[0]: row[1] for row in result}

    async def get_tag_values(self, key: str) -> dict[str, int]:
        """Return all distinct values for a tag key with usage counts."""
        result = await self._session.execute(
            text(
                "SELECT tags->>:key AS val, COUNT(*) as cnt "
                "FROM data_sources "
                "WHERE tags ? :key "
                "GROUP BY val ORDER BY cnt DESC"
            ),
            {"key": key},
        )
        return {row[0]: row[1] for row in result}
