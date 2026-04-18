"""Annotation repository — DB access for evaluation annotations."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from tropek.cache.redis_cache import RedisCache
from tropek.db.models import EvaluationAnnotation, SLOEvaluation


class AnnotationRepository:
    """Data access layer for evaluation annotations."""

    def __init__(self, session: AsyncSession, cache: RedisCache | None = None) -> None:
        self._session = session
        self._cache = cache

    async def add_annotation(
        self,
        slo_evaluation_id: uuid.UUID,
        *,
        content: str,
        category_id: uuid.UUID,
        author: str | None = None,
        tags: dict[str, Any] | None = None,
        note_group_id: uuid.UUID | None = None,
        note_group_name: str | None = None,
    ) -> EvaluationAnnotation:
        """Append an SLO-level annotation (used by re-eval and per-SLO flows)."""
        ann = EvaluationAnnotation(
            id=uuid.uuid4(),
            slo_evaluation_id=slo_evaluation_id,
            content=content,
            author=author,
            category_id=category_id,
            tags=tags or {},
            note_group_id=note_group_id,
            note_group_name=note_group_name,
        )
        self._session.add(ann)
        await self._session.flush()
        if self._cache:
            await self._cache.invalidate(f'annot_count:{slo_evaluation_id}')
            await self._cache.invalidate(f'annot_latest:{slo_evaluation_id}')
        return ann

    async def add_run_annotation(
        self,
        evaluation_run_id: uuid.UUID,
        *,
        content: str,
        category_id: uuid.UUID,
        author: str | None = None,
        tags: dict[str, Any] | None = None,
        note_group_id: uuid.UUID | None = None,
        note_group_name: str | None = None,
    ) -> EvaluationAnnotation:
        """Append a run-level annotation (column-level notes from the UI)."""
        ann = EvaluationAnnotation(
            id=uuid.uuid4(),
            evaluation_run_id=evaluation_run_id,
            content=content,
            author=author,
            category_id=category_id,
            tags=tags or {},
            note_group_id=note_group_id,
            note_group_name=note_group_name,
        )
        self._session.add(ann)
        await self._session.flush()
        return ann

    async def list_for_trend(
        self,
        *,
        asset_id: uuid.UUID,
        slo_name: str,
    ) -> tuple[list[EvaluationAnnotation], dict[uuid.UUID, list[uuid.UUID]]]:
        """Return non-hidden annotations across all runs for (asset, slo).

        Combines run-level annotations (attached to EvaluationRun) and SLO-level
        annotations (attached to SLOEvaluation). Each SLO evaluation matching the
        (asset_id, slo_name) pair contributes both its own annotations and the
        annotations on its parent run.

        Also returns a run_id → [slo_eval_id, ...] mapping scoped to this
        (asset, slo), so run-level annotations can be fanned out to every
        trend point (trend points are keyed by slo_evaluation_id).
        """
        slo_evals = await self._session.execute(
            select(SLOEvaluation.id, SLOEvaluation.evaluation_id)
            .where(SLOEvaluation.asset_id == asset_id)
            .where(SLOEvaluation.slo_name == slo_name)
        )
        slo_eval_ids: list[uuid.UUID] = []
        run_to_slo_evals: dict[uuid.UUID, list[uuid.UUID]] = {}
        for slo_eval_id, evaluation_id in slo_evals.all():
            slo_eval_ids.append(slo_eval_id)
            run_to_slo_evals.setdefault(evaluation_id, []).append(slo_eval_id)

        if not slo_eval_ids and not run_to_slo_evals:
            return [], {}

        result = await self._session.execute(
            select(EvaluationAnnotation)
            .options(selectinload(EvaluationAnnotation.category))
            .where(EvaluationAnnotation.hidden_at.is_(None))
            .where(
                (EvaluationAnnotation.slo_evaluation_id.in_(slo_eval_ids))
                | (EvaluationAnnotation.evaluation_run_id.in_(list(run_to_slo_evals.keys())))
            )
            .order_by(EvaluationAnnotation.created_at)
        )
        return list(result.scalars().all()), run_to_slo_evals

    async def list_for_run(self, run_id: uuid.UUID) -> list[EvaluationAnnotation]:
        """Return non-hidden run-level annotations for an EvaluationRun."""
        result = await self._session.execute(
            select(EvaluationAnnotation)
            .options(selectinload(EvaluationAnnotation.category))
            .where(EvaluationAnnotation.evaluation_run_id == run_id)
            .where(EvaluationAnnotation.hidden_at.is_(None))
            .order_by(EvaluationAnnotation.created_at)
        )
        return list(result.scalars().all())

    async def get_annotation_by_id(self, annotation_id: uuid.UUID) -> EvaluationAnnotation | None:
        """Fetch a single annotation by its ID."""
        result = await self._session.execute(
            select(EvaluationAnnotation)
            .options(selectinload(EvaluationAnnotation.category))
            .where(EvaluationAnnotation.id == annotation_id)
        )
        return result.scalar_one_or_none()

    async def update_annotation(
        self,
        annotation_id: uuid.UUID,
        *,
        content: str | None = None,
        author: str | None = None,
        category_id: uuid.UUID | None = None,
        tags: dict[str, Any] | None = None,
    ) -> EvaluationAnnotation | None:
        """Update mutable annotation fields."""
        values: dict[str, Any] = {}
        if content is not None:
            values['content'] = content
        if author is not None:
            values['author'] = author
        if category_id is not None:
            values['category_id'] = category_id
        if tags is not None:
            values['tags'] = tags
        if values:
            await self._session.execute(
                update(EvaluationAnnotation).where(EvaluationAnnotation.id == annotation_id).values(**values)
            )
            await self._session.flush()
        ann = await self.get_annotation_by_id(annotation_id)
        if self._cache and ann is not None and ann.slo_evaluation_id is not None:
            await self._cache.invalidate(f'annot_count:{ann.slo_evaluation_id}')
            await self._cache.invalidate(f'annot_latest:{ann.slo_evaluation_id}')
        return ann

    async def hide_annotation(
        self,
        annotation_id: uuid.UUID,
        *,
        reason: str,
        author: str | None = None,
    ) -> EvaluationAnnotation | None:
        """Soft-delete an annotation by setting hidden_at.

        Args:
            annotation_id: Annotation to hide.
            reason: Why the annotation is being hidden.
            author: Who hid the annotation.

        Returns:
            Updated annotation or None if not found.
        """
        await self._session.execute(
            update(EvaluationAnnotation)
            .where(EvaluationAnnotation.id == annotation_id)
            .values(
                hidden_at=func.now(),
                hidden_by=author,
                hidden_reason=reason,
            )
        )
        await self._session.flush()
        ann = await self.get_annotation_by_id(annotation_id)
        if self._cache and ann is not None and ann.slo_evaluation_id is not None:
            await self._cache.invalidate(f'annot_count:{ann.slo_evaluation_id}')
            await self._cache.invalidate(f'annot_latest:{ann.slo_evaluation_id}')
        return ann
