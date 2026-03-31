"""Repository for parent EvaluationRun CRUD and child result rollup."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EvaluationRun, SLOEvaluation

_RESULT_RANK: dict[str, int] = {'pass': 0, 'warning': 1, 'fail': 2, 'error': 3}


class EvaluationRunRepository:
    """Data access for parent EvaluationRun rows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        asset_id: uuid.UUID,
        eval_name: str,
        period_start: datetime,
        period_end: datetime,
    ) -> EvaluationRun:
        """Create a new pending EvaluationRun."""
        run = EvaluationRun(
            id=uuid.uuid4(),
            asset_id=asset_id,
            eval_name=eval_name,
            period_start=period_start,
            period_end=period_end,
            status='pending',
        )
        self._session.add(run)
        await self._session.flush()
        return run

    async def get_by_id(self, run_id: uuid.UUID) -> EvaluationRun | None:
        """Fetch an EvaluationRun by primary key."""
        return await self._session.get(EvaluationRun, run_id)

    async def mark_completed(
        self,
        run_id: uuid.UUID,
        *,
        result: str,
        achieved_points: int | None = None,
        total_points: int | None = None,
    ) -> None:
        """Directly mark an EvaluationRun as completed with a given result."""
        await self._session.execute(
            update(EvaluationRun)
            .where(EvaluationRun.id == run_id)
            .values(
                status='completed',
                result=result,
                achieved_points=achieved_points,
                total_points=total_points,
            )
        )

    async def mark_running(self, run_id: uuid.UUID) -> None:
        """Transition status to running (first child started)."""
        await self._session.execute(
            update(EvaluationRun)
            .where(EvaluationRun.id == run_id)
            .values(status='running')
        )

    async def rollup_if_all_done(self, run_id: uuid.UUID) -> EvaluationRun | None:
        """Aggregate child results if all SLO evaluations are completed or failed.

        Returns the updated EvaluationRun if rollup happened, None if children
        are still in progress.
        """
        q = select(SLOEvaluation).where(SLOEvaluation.evaluation_id == run_id)
        result = await self._session.execute(q)
        children = list(result.scalars().all())

        if not children:
            return None

        pending_statuses = {'pending', 'running', 'partial'}
        if any(c.status in pending_statuses for c in children):
            return None

        worst_result: str | None = None
        achieved = 0
        total = 0
        for child in children:
            if child.result and (
                worst_result is None
                or _RESULT_RANK.get(child.result, 0) > _RESULT_RANK.get(worst_result, 0)
            ):
                worst_result = child.result
            achieved += child.achieved_points or 0
            total += child.total_points or 0

        await self._session.execute(
            update(EvaluationRun)
            .where(EvaluationRun.id == run_id)
            .values(
                status='completed',
                result=worst_result,
                achieved_points=achieved or None,
                total_points=total or None,
            )
        )
        # Expire the cached instance so get_by_id re-fetches updated values.
        existing = await self._session.get(EvaluationRun, run_id)
        if existing is not None:
            await self._session.refresh(existing)
        return existing
