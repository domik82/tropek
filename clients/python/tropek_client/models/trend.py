"""Metric trend series models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from tropek_client.models.change_points import ChangePointMarker


class TrendTargetEntry(BaseModel):
    """A single pass/warn target entry in a trend point."""

    criteria: str
    target_value: float | int
    violated: bool


class TrendTargets(BaseModel):
    """Pass and warning targets for a trend point."""

    var_pass: list[TrendTargetEntry] | None = Field(default=None, alias='pass')
    warn: list[TrendTargetEntry] | None = None


class TrendPoint(BaseModel):
    """A single data point in a metric trend series."""

    timestamp: datetime
    value: float | int
    score: float | int
    eval_id: UUID
    result: str
    baseline: float | int | None = None
    evaluation_name: str | None = None
    targets: TrendTargets | None = None
    change_point: ChangePointMarker | None = None
