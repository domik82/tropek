"""Repository for normalized indicator_results table."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import IndicatorResultRow


class IndicatorRepository:
    """CRUD for per-SLI evaluation results (normalized table)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def bulk_insert(
        self,
        slo_evaluation_id: uuid.UUID,
        rows: list[dict[str, Any]],
    ) -> None:
        """Insert indicator result rows for a single SLO evaluation."""
        for row in rows:
            self._session.add(
                IndicatorResultRow(
                    slo_evaluation_id=slo_evaluation_id,
                    slo_objective_id=row['slo_objective_id'],
                    value=row.get('value'),
                    compared_value=row.get('compared_value'),
                    change_absolute=row.get('change_absolute'),
                    change_relative_pct=row.get('change_relative_pct'),
                    status=row['status'],
                    score=row.get('score', 0.0),
                )
            )
        await self._session.flush()

    async def delete_for_evaluation(self, slo_evaluation_id: uuid.UUID) -> None:
        """Delete all indicator rows for a SLO evaluation (used by re-evaluation)."""
        await self._session.execute(
            delete(IndicatorResultRow).where(IndicatorResultRow.slo_evaluation_id == slo_evaluation_id)
        )
        await self._session.flush()
