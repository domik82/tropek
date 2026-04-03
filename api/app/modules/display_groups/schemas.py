"""Pydantic schemas for SLO display groups."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.modules.common.schemas import StrictInput


class DisplayGroupCreate(StrictInput):
    name: str
    display_name: str | None = None
    parent_id: uuid.UUID | None = None
    sort_order: int = 0


class DisplayGroupRead(BaseModel):
    id: uuid.UUID
    name: str
    display_name: str | None
    parent_id: uuid.UUID | None
    sort_order: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DisplayGroupMemberAdd(StrictInput):
    slo_name: str
