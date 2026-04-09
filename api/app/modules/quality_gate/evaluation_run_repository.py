"""Repository for parent EvaluationRun CRUD and child result finalization."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import exists, select, update
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

    async def finalize_if_all_done(self, run_id: uuid.UUID) -> EvaluationRun | None:
        """Finalize parent run by aggregating child results.

        Returns the updated EvaluationRun if finalized, None if children
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

    async def find_finalizable_pending_ids(self, *, limit: int) -> list[uuid.UUID]:
        """Return IDs of parent runs whose children are all terminal but status is not 'completed'.

        Ordered by period_end ASC so the oldest stuck runs are rescued first.
        Takes no row locks — safe to call concurrently with live child updates.
        """
        pending_statuses = ('pending', 'running', 'partial')
        has_any_child = exists().where(SLOEvaluation.evaluation_id == EvaluationRun.id)
        has_pending_child = (
            exists()
            .where(SLOEvaluation.evaluation_id == EvaluationRun.id)
            .where(SLOEvaluation.status.in_(pending_statuses))
        )
        q = (
            select(EvaluationRun.id)
            .where(EvaluationRun.status != 'completed')
            .where(has_any_child)
            .where(~has_pending_child)
            .order_by(EvaluationRun.period_end.asc())
            .limit(limit)
        )
        result = await self._session.execute(q)
        return list(result.scalars().all())
