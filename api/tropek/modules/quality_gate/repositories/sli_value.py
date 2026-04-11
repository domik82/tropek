"""SLI value repository — DB access for SLI metric values."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from tropek.db.models import SLIValue


class SLIValueRepository:
    """Data access layer for SLI metric values."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def write_sli_values(self, rows: list[dict[str, Any]]) -> None:
        """Batch insert SLI value rows.

        Args:
            rows: List of dicts matching SLIValue columns (slo_evaluation_id, eval_start,
                  metric_name, aggregation, value, asset_name, evaluation_name, os_tag).
        """
        if not rows:
            return
        await self._session.execute(insert(SLIValue).values(rows))

    async def delete_sli_values(self, slo_evaluation_id: uuid.UUID) -> None:
        """Delete all SLI values for an evaluation (hard rerun).

        Args:
            slo_evaluation_id: Evaluation whose SLI values should be deleted.
        """
        await self._session.execute(delete(SLIValue).where(SLIValue.slo_evaluation_id == slo_evaluation_id))

    async def get_sli_values_for_eval(self, slo_evaluation_id: uuid.UUID) -> list[SLIValue]:
        """Fetch all SLI values for a given evaluation.

        Args:
            slo_evaluation_id: Evaluation UUID.

        Returns:
            All SLIValue rows for this evaluation.
        """
        result = await self._session.execute(select(SLIValue).where(SLIValue.slo_evaluation_id == slo_evaluation_id))
        return list(result.scalars().all())
