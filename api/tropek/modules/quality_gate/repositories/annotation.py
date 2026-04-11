"""Annotation repository — DB access for evaluation annotations."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from tropek.cache.redis_cache import RedisCache
from tropek.db.models import EvaluationAnnotation


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
        author: str | None = None,
        category: str | None = None,
        tags: dict[str, Any] | None = None,
    ) -> EvaluationAnnotation:
        """Append an annotation to an evaluation.

        Args:
            slo_evaluation_id: Evaluation to annotate.
            content: Note text (required).
            author: Optional identifier of who wrote the annotation.
            category: Optional free label (e.g. "environment", "deployment").
            tags: Optional arbitrary tags.

        Returns:
            Newly created EvaluationAnnotation.
        """
        ann = EvaluationAnnotation(
            id=uuid.uuid4(),
            slo_evaluation_id=slo_evaluation_id,
            content=content,
            author=author,
            category=category,
            tags=tags or {},
        )
        self._session.add(ann)
        await self._session.flush()
        if self._cache:
            await self._cache.invalidate(f'annot_count:{slo_evaluation_id}')
            await self._cache.invalidate(f'annot_latest:{slo_evaluation_id}')
        return ann

    async def get_annotation_by_id(self, annotation_id: uuid.UUID) -> EvaluationAnnotation | None:
        """Fetch a single annotation by its ID."""
        result = await self._session.execute(
            select(EvaluationAnnotation).where(EvaluationAnnotation.id == annotation_id)
        )
        return result.scalar_one_or_none()

    async def update_annotation(
        self,
        annotation_id: uuid.UUID,
        *,
        content: str | None = None,
        author: str | None = None,
        category: str | None = None,
        tags: dict[str, Any] | None = None,
    ) -> EvaluationAnnotation | None:
        """Update mutable annotation fields."""
        values: dict[str, Any] = {}
        if content is not None:
            values['content'] = content
        if author is not None:
            values['author'] = author
        if category is not None:
            values['category'] = category
        if tags is not None:
            values['tags'] = tags
        if values:
            await self._session.execute(
                update(EvaluationAnnotation).where(EvaluationAnnotation.id == annotation_id).values(**values)
            )
            await self._session.flush()
        return await self.get_annotation_by_id(annotation_id)

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
        if self._cache and ann is not None:
            await self._cache.invalidate(f'annot_count:{ann.slo_evaluation_id}')
            await self._cache.invalidate(f'annot_latest:{ann.slo_evaluation_id}')
        return ann
