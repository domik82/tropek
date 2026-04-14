"""Pydantic schemas for evaluation annotations."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from tropek.modules.common.schemas import StrictInput


class AnnotationRead(BaseModel):
    """Response schema for an evaluation annotation.

    Exactly one of slo_evaluation_id / evaluation_run_id is set. SLO-level notes come
    from re-eval (per-SLO deltas); run-level notes come from the UI column form.
    """

    id: uuid.UUID
    slo_evaluation_id: uuid.UUID | None
    evaluation_run_id: uuid.UUID | None
    content: str
    author: str | None
    category: str | None
    tags: dict[str, Any]
    note_group_id: uuid.UUID | None
    note_group_name: str | None
    hidden_at: datetime | None
    hidden_by: str | None
    hidden_reason: str | None
    created_at: datetime
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class AnnotationCreate(StrictInput):
    """Request body for creating an annotation."""

    content: str
    author: str | None = None
    category: str | None = None
    tags: dict[str, Any] = {}


class AnnotationUpdate(StrictInput):
    """Request body for updating an annotation."""

    content: str | None = None
    author: str | None = None
    category: str | None = None
    tags: dict[str, Any] | None = None


class AnnotationHide(StrictInput):
    """Request body for soft-deleting (hiding) an annotation."""

    reason: str
    author: str | None = None
