"""Pydantic schemas for annotation categories."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictBool

from tropek.modules.common.schemas import StrictInput


class CategoryColor(StrEnum):
    """Allowed color tokens for an annotation category."""

    SKY = 'sky'
    GREEN = 'green'
    AMBER = 'amber'
    RED = 'red'
    PURPLE = 'purple'
    PINK = 'pink'
    SLATE = 'slate'
    GRAY = 'gray'


LabelStr = Annotated[str, Field(min_length=1, max_length=12, pattern=r'^[^\x00]+$')]
NameStr = Annotated[str, Field(min_length=1, max_length=40, pattern=r'^[a-z][a-z0-9\-]*$')]


class AnnotationCategoryRead(BaseModel):
    """Category record as returned by the API."""

    id: uuid.UUID
    name: str
    label: str
    color: CategoryColor
    show_on_graph: bool
    is_system: bool
    created_at: datetime
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class AnnotationCategoryCreate(StrictInput):
    """Request body for creating a user-defined category."""

    name: NameStr
    label: LabelStr
    color: CategoryColor
    show_on_graph: StrictBool = True


class AnnotationCategoryUpdate(StrictInput):
    """Request body for patching category fields."""

    name: NameStr | None = None
    label: LabelStr | None = None
    color: CategoryColor | None = None
    show_on_graph: StrictBool | None = None
