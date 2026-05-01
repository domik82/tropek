"""Annotation and annotation category models."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from tropek_client.models.common import CategoryColor


class AnnotationCategoryCreate(BaseModel):
    """Input model for creating an annotation category."""

    name: str
    label: str
    color: CategoryColor
    show_on_graph: bool = True


class AnnotationCategoryRead(BaseModel):
    """Read model for an annotation category."""

    id: UUID
    name: str
    label: str
    color: CategoryColor
    show_on_graph: bool
    is_system: bool
    created_at: datetime
    updated_at: datetime | None = None


class AnnotationCategoryUpdate(BaseModel):
    """Input model for updating an annotation category."""

    name: str | None = None
    label: str | None = None
    color: CategoryColor | None = None
    show_on_graph: bool | None = None


class AnnotationCreate(BaseModel):
    """Input model for creating an annotation."""

    content: str
    author: str | None = None
    category_id: UUID
    tags: dict[str, Any] | None = None


class AnnotationRead(BaseModel):
    """Read model for an annotation."""

    id: UUID
    slo_evaluation_id: UUID | None = None
    evaluation_run_id: UUID | None = None
    content: str
    author: str | None = None
    category_id: UUID
    category: AnnotationCategoryRead
    tags: dict[str, Any]
    note_group_id: UUID | None = None
    note_group_name: str | None = None
    hidden_at: datetime | None = None
    hidden_by: str | None = None
    hidden_reason: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class AnnotationUpdate(BaseModel):
    """Input model for updating an annotation."""

    content: str | None = None
    author: str | None = None
    category_id: UUID | None = None
    tags: dict[str, Any] | None = None


class AnnotationHide(BaseModel):
    """Input model for hiding an annotation."""

    reason: str
    author: str | None = None
