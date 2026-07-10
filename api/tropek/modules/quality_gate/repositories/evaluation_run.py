"""Repository for parent EvaluationRun CRUD and child result finalization."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, cast

from sqlalchemy import CursorResult, exists, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from tropek.db.models import EvaluationRun, SLOEvaluation
from tropek.modules.quality_gate.evaluation_engine.constants import RESULT_RANK, EvaluationStatus


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
        compare_to: dict[str, str] | None = None,
    ) -> EvaluationRun:
        """Create a new pending EvaluationRun."""
        run = EvaluationRun(
            id=uuid.uuid4(),
            asset_id=asset_id,
            eval_name=eval_name,
            period_start=period_start,
            period_end=period_end,
            status=EvaluationStatus.PENDING,
            compare_to=compare_to,
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
                status=EvaluationStatus.COMPLETED,
                result=result,
                achieved_points=achieved_points,
                total_points=total_points,
            )
        )

    async def mark_running(self, run_id: uuid.UUID) -> None:
        """Transition status to running (first child started)."""
        await self._session.execute(
            update(EvaluationRun).where(EvaluationRun.id == run_id).values(status=EvaluationStatus.RUNNING)
        )

    async def finalize_if_all_done(self, run_id: uuid.UUID) -> EvaluationRun | None:
        """Finalize parent run by aggregating child results.

        Every child job enqueues its own finalize attempt, so this runs ~once per
        child. It stays correct but avoids the redundant work / hot-row lock
        contention that all-children-finalize-at-once would otherwise cause:

        - early-out if the parent is already COMPLETED (skips the child scan);
        - the finalizing UPDATE is guarded by ``status != COMPLETED`` so only the
          first attempt to win the row lock writes — concurrent duplicates match
          zero rows and produce no WAL write.

        Returns the updated EvaluationRun only for the attempt that actually
        finalized it; None otherwise (already done, still in progress, or it lost
        the race to a concurrent finalize).
        """
        existing = await self._session.get(EvaluationRun, run_id)
        if existing is None or existing.status == EvaluationStatus.COMPLETED:
            return None

        # Column-only select: finalize needs just these fields. Selecting the ORM entity
        # would trigger the lazy='selectin' load of every child's indicator_rows (unused
        # here) — a heavy over-fetch that ran ~once per child and held the parent-run row
        # lock across it. Rows expose the columns by name, so the aggregation below is unchanged.
        q = select(
            SLOEvaluation.status,
            SLOEvaluation.result,
            SLOEvaluation.achieved_points,
            SLOEvaluation.total_points,
        ).where(SLOEvaluation.evaluation_id == run_id)
        result = await self._session.execute(q)
        children = list(result.all())

        if not children:
            return None

        pending_statuses = {EvaluationStatus.PENDING, EvaluationStatus.RUNNING, EvaluationStatus.PARTIAL}
        if any(child.status in pending_statuses for child in children):
            return None

        worst_result: str | None = None
        achieved = 0
        total = 0
        for child in children:
            if child.result and (
                worst_result is None or RESULT_RANK.get(child.result, 0) > RESULT_RANK.get(worst_result, 0)
            ):
                worst_result = child.result
            achieved += child.achieved_points or 0
            total += child.total_points or 0

        # execute() is typed as Result, but a Core UPDATE yields a CursorResult
        # exposing rowcount — cast so mypy sees the runtime type.
        update_result = cast(
            'CursorResult[Any]',
            await self._session.execute(
                update(EvaluationRun)
                .where(EvaluationRun.id == run_id)
                .where(EvaluationRun.status != EvaluationStatus.COMPLETED)
                .values(
                    status=EvaluationStatus.COMPLETED,
                    result=worst_result,
                    achieved_points=achieved or None,
                    total_points=total or None,
                )
            ),
        )
        if update_result.rowcount == 0:
            # A concurrent finalize completed the run between our read and update.
            return None
        await self._session.refresh(existing)
        return existing

    async def find_finalizable_pending_ids(self, *, limit: int) -> list[uuid.UUID]:
        """Return IDs of parent runs whose children are all terminal but status is not 'completed'.

        Ordered by period_end ASC so the oldest stuck runs are rescued first.
        Takes no row locks — safe to call concurrently with live child updates.
        """
        pending_statuses = (EvaluationStatus.PENDING, EvaluationStatus.RUNNING, EvaluationStatus.PARTIAL)
        has_any_child = exists().where(SLOEvaluation.evaluation_id == EvaluationRun.id)
        has_pending_child = (
            exists()
            .where(SLOEvaluation.evaluation_id == EvaluationRun.id)
            .where(SLOEvaluation.status.in_(pending_statuses))
        )
        q = (
            select(EvaluationRun.id)
            .where(EvaluationRun.status != EvaluationStatus.COMPLETED)
            .where(has_any_child)
            .where(~has_pending_child)
            .order_by(EvaluationRun.period_end.asc())
            .limit(limit)
        )
        result = await self._session.execute(q)
        return list(result.scalars().all())
