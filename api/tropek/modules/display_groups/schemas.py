"""Pydantic schemas for SLO display groups."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from tropek.modules.common.schemas import IntNotBool, SafeStr, StrictInput

_INT32_SORT_ORDER = Annotated[IntNotBool, Field(ge=-(2**31), le=2**31 - 1)]


class DisplayGroupCreate(StrictInput):
    """Request body for creating a display group."""

    name: SafeStr
    display_name: SafeStr | None = None
    parent_id: uuid.UUID | None = None
    sort_order: _INT32_SORT_ORDER = 0


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

    slo_name: SafeStr
