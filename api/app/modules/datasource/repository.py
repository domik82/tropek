"""DataSource repository — CRUD for data_sources table."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, select
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

    async def list_all(self) -> list[DataSource]:
        """Return all registered datasources ordered by name.

        Returns:
            All DataSource records.
        """
        result = await self._session.execute(select(DataSource).order_by(DataSource.name))
        return list(result.scalars().all())

    async def delete(self, datasource_id: uuid.UUID) -> None:
        """Hard-delete a datasource record.

        Args:
            datasource_id: UUID of the datasource to remove.
        """
        await self._session.execute(delete(DataSource).where(DataSource.id == datasource_id))
