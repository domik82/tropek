"""Pydantic schemas for SLO display groups."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.modules.common.schemas import StrictInput


class DisplayGroupCreate(StrictInput):
    """Request body for creating a display group."""

    name: str
    display_name: str | None = None
    parent_id: uuid.UUID | None = None
    sort_order: int = 0


class DisplayGroupRead(BaseModel):
    """Response schema for a display group."""

    id: uuid.UUID
    name: str
    display_name: str | None
    parent_id: uuid.UUID | None
    sort_order: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DisplayGroupMemberAdd(StrictInput):
    """Request body for adding an SLO to a display group."""

    slo_name: str
