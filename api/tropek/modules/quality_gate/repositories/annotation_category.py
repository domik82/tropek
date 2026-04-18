"""Annotation category repository — CRUD for annotation_categories."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from tropek.db.models import AnnotationCategory, EvaluationAnnotation


class SystemCategoryError(Exception):
    """Raised when attempting to mutate a system category in a disallowed way."""


class CategoryInUseError(Exception):
    """Raised when a category is referenced and cannot be deleted."""


class AnnotationCategoryRepository:
    """Data access for the annotation_categories table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self) -> list[AnnotationCategory]:
        """Return every category, sorted alphabetically by name."""
        result = await self._session.execute(
            select(AnnotationCategory).order_by(AnnotationCategory.name)
        )
        return list(result.scalars().all())

    async def get_by_id(self, category_id: uuid.UUID) -> AnnotationCategory | None:
        """Return the category with the given id, or None."""
        result = await self._session.execute(
            select(AnnotationCategory).where(AnnotationCategory.id == category_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> AnnotationCategory | None:
        """Return the category with the given unique name, or None."""
        result = await self._session.execute(
            select(AnnotationCategory).where(AnnotationCategory.name == name)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        name: str,
        label: str,
        color: str,
        show_on_graph: bool = True,
    ) -> AnnotationCategory:
        """Insert a new user-defined (non-system) category."""
        row = AnnotationCategory(
            id=uuid.uuid4(),
            name=name,
            label=label,
            color=color,
            show_on_graph=show_on_graph,
            is_system=False,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def update(
        self,
        category_id: uuid.UUID,
        *,
        name: str | None = None,
        label: str | None = None,
        color: str | None = None,
        show_on_graph: bool | None = None,
    ) -> AnnotationCategory:
        """Patch an existing category; reject renaming a system row."""
        row = await self.get_by_id(category_id)
        if row is None:
            raise LookupError(f'category {category_id} not found')
        if row.is_system and name is not None and name != row.name:
            raise SystemCategoryError('cannot rename a system category')

        values: dict[str, object] = {}
        if name is not None:
            values['name'] = name
        if label is not None:
            values['label'] = label
        if color is not None:
            values['color'] = color
        if show_on_graph is not None:
            values['show_on_graph'] = show_on_graph
        if values:
            await self._session.execute(
                update(AnnotationCategory)
                .where(AnnotationCategory.id == category_id)
                .values(**values)
            )
            await self._session.flush()
        refreshed = await self.get_by_id(category_id)
        assert refreshed is not None
        return refreshed

    async def delete(self, category_id: uuid.UUID) -> int:
        """Delete a non-system category, reassigning its annotations to 'info'.

        Returns the number of annotations reassigned.
        """
        row = await self.get_by_id(category_id)
        if row is None:
            raise LookupError(f'category {category_id} not found')
        if row.is_system:
            raise SystemCategoryError('cannot delete a system category')

        info = await self.get_by_name('info')
        if info is None:
            raise LookupError("default 'info' category missing")

        reassigned_result = await self._session.execute(
            update(EvaluationAnnotation)
            .where(EvaluationAnnotation.category_id == category_id)
            .values(category_id=info.id)
        )
        await self._session.execute(
            delete(AnnotationCategory).where(AnnotationCategory.id == category_id)
        )
        await self._session.flush()
        rowcount = getattr(reassigned_result, 'rowcount', 0)
        return int(rowcount or 0)
