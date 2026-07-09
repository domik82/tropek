"""Change point detection models."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from tropek_client.models.common import Direction, Transition


class ChangePointMarker(BaseModel):
    """Marker indicating a change point on a metric."""

    direction: Direction
    change_relative_pct: float | int | None = None
    transition: Transition | None = None


class ChangePointRead(BaseModel):
    """Read model for a detected change point."""

    id: UUID
    asset_id: UUID
    slo_name: str
    metric_name: str
    period_start: datetime
    period_end: datetime | None = None
    detector: str
    direction: Direction
    change_relative_pct: float | int | None
    transition: Transition | None = None
    change_absolute: float | int
    pvalue: float | int
    pre_segment_mean: float | int
    post_segment_mean: float | int
    post_segment_std: float | int
    status: str
    triage_author: str | None = None
    triage_note: str | None = None
    triage_at: datetime | None = None
    linked_ticket: str | None = None
    found_by_evaluation_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
