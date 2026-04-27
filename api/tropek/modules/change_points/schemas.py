"""Pydantic schemas for change point API requests and responses."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from tropek.modules.change_points.detector import Direction
from tropek.modules.common.schemas import StrictInput


class ChangePointMarker(BaseModel):
    """Lightweight marker attached to heatmap cells and trend points."""

    direction: Direction
    change_relative_pct: float


class ChangePointRead(BaseModel):
    """Full change point detail for list views and detail endpoint."""

    id: uuid.UUID
    asset_id: uuid.UUID
    slo_name: str
    metric_name: str
    period_start: datetime
    detector: str
    direction: Direction
    change_relative_pct: float
    change_absolute: float
    pvalue: float = Field(validation_alias='t_statistic')
    pre_segment_mean: float
    post_segment_mean: float
    post_segment_std: float
    status: str
    triage_author: str | None
    triage_note: str | None
    triage_at: datetime | None
    linked_ticket: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {'from_attributes': True}


class TriageRequest(StrictInput):
    """Request body for triaging a change point."""

    status: str
    triage_note: str | None = None
    linked_ticket: str | None = None
    triage_author: str | None = None


class BulkTriageRequest(StrictInput):
    """Request body for bulk-triaging change points."""

    ids: list[uuid.UUID]
    status: str
    triage_note: str | None = None
    triage_author: str | None = None


class ChangePointConfigInput(StrictInput):
    """Optional overrides for change point detection — used in SLO YAML change_point: block."""

    enabled: bool | None = None
    higher_is_better: bool | None = None
    window_size: int | None = Field(default=None, strict=True)
    max_pvalue: float | None = None
    min_magnitude: float | None = None
    min_sample_size: int | None = Field(default=None, strict=True)


class ChangePointConfigRead(BaseModel):
    """Full resolved change point config for an objective."""

    slo_objective_id: uuid.UUID
    enabled: bool
    higher_is_better: bool
    window_size: int
    max_pvalue: float
    min_magnitude: float
    min_sample_size: int

    model_config = {'from_attributes': True}
