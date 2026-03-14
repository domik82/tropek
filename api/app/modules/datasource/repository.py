"""DataSource repository — CRUD for data_sources table."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, select, update
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
        labels: dict[str, Any] | None = None,
    ) -> DataSource:
        """Register a new datasource.

        Args:
            name: Unique name for this datasource registration.
            adapter_type: The adapter kind (e.g. "prometheus").
            adapter_url: Base URL of the running adapter service.
            display_name: Optional human-readable label.
            labels: Optional free-form metadata labels.

        Returns:
            The newly created DataSource record.
        """
        ds = DataSource(
            id=uuid.uuid4(),
            name=name,
            display_name=display_name,
            adapter_type=adapter_type,
            adapter_url=adapter_url,
            labels=labels or {},
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

    async def list_all(self, *, adapter_type: str | None = None) -> list[DataSource]:
        """Return all registered datasources, optionally filtered by adapter type.

        Args:
            adapter_type: When given, only return datasources of this adapter kind.

        Returns:
            Matching DataSource records ordered by name.
        """
        q = select(DataSource).order_by(DataSource.name)
        if adapter_type:
            q = q.where(DataSource.adapter_type == adapter_type)
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def update(
        self,
        name: str,
        *,
        display_name: str | None = None,
        adapter_url: str | None = None,
        labels: dict[str, Any] | None = None,
    ) -> DataSource | None:
        """Update mutable fields on an existing DataSource. Returns None if not found.

        Args:
            name: Unique datasource name to update.
            display_name: New human-readable label, if changing.
            adapter_url: New adapter base URL, if changing.
            labels: New labels dict, if changing.

        Returns:
            Updated DataSource, or None if not found.
        """
        values: dict[str, Any] = {}
        if display_name is not None:
            values["display_name"] = display_name
        if adapter_url is not None:
            values["adapter_url"] = adapter_url
        if labels is not None:
            values["labels"] = labels
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
