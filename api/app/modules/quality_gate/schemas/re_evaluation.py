"""Pydantic schemas for the re-evaluation endpoint."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, model_validator

from app.modules.common.schemas import StrictInput


class ReEvaluateRequest(StrictInput):
    """Request body for POST /evaluations/re-evaluate."""

    asset_name: str
    slo_name: str

    # Scope — exactly one required
    from_date: datetime | None = None
    from_baseline: bool = False
    from_evaluation_id: uuid.UUID | None = None

    # Optional
    slo_version: int | None = None
    dry_run: bool = False
    pin_strategy: Literal['skip_to_pin', 'ignore_pin'] | None = None

    @model_validator(mode='after')
    def exactly_one_scope(self) -> ReEvaluateRequest:
        """Ensure exactly one scope parameter is provided."""
        scopes = sum(
            [
                self.from_date is not None,
                self.from_baseline,
                self.from_evaluation_id is not None,
            ]
        )
        if scopes != 1:
            msg = 'exactly one of from_date, from_baseline, or from_evaluation_id is required'
            raise ValueError(msg)
        return self


class BaselinePinConflictError(Exception):
    """Raised when re-evaluation from_date is before the active baseline pin."""

    def __init__(self, pin_date: datetime, pin_evaluation_id: uuid.UUID) -> None:
        self.pin_date = pin_date
        self.pin_evaluation_id = pin_evaluation_id
        super().__init__('re-evaluation start date is before the active baseline pin')


class ReEvalResultItem(BaseModel):
    """One re-evaluated evaluation in the response."""

    id: uuid.UUID
    evaluation_name: str
    period_start: datetime
    period_end: datetime
    old_result: str
    new_result: str
    old_score: float
    new_score: float


class ReEvaluateResponse(BaseModel):
    """Response body for POST /evaluations/re-evaluate."""

    affected_evaluations: int
    slo_version_used: int
    results: list[ReEvalResultItem]
