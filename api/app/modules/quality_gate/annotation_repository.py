"""Annotation repository — DB access for evaluation annotations."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EvaluationAnnotation


class AnnotationRepository:
    """Data access layer for evaluation annotations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_annotation(
        self,
        eval_id: uuid.UUID,
        *,
        content: str,
        author: str | None = None,
        category: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> EvaluationAnnotation:
        """Append an annotation to an evaluation.

        Args:
            eval_id: Evaluation to annotate.
            content: Note text (required).
            author: Optional identifier of who wrote the annotation.
            category: Optional free label (e.g. "environment", "deployment").
            meta: Optional arbitrary metadata.

        Returns:
            Newly created EvaluationAnnotation.
        """
        ann = EvaluationAnnotation(
            id=uuid.uuid4(),
            evaluation_id=eval_id,
            content=content,
            author=author,
            category=category,
            meta=meta or {},
        )
        self._session.add(ann)
        await self._session.flush()
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
        meta: dict[str, Any] | None = None,
    ) -> EvaluationAnnotation | None:
        """Update mutable annotation fields."""
        values: dict[str, Any] = {}
        if content is not None:
            values["content"] = content
        if author is not None:
            values["author"] = author
        if category is not None:
            values["category"] = category
        if meta is not None:
            values["meta"] = meta
        if values:
            await self._session.execute(
                update(EvaluationAnnotation)
                .where(EvaluationAnnotation.id == annotation_id)
                .values(**values)
            )
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
        return await self.get_annotation_by_id(annotation_id)
