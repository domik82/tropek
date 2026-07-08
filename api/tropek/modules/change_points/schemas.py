"""Pydantic schemas for change point API requests and responses."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, StrictBool

from tropek.modules.change_points.detector import Direction, Transition
from tropek.modules.common.schemas import FloatNotBool, IntNotBool, SafeStr, StrictInput


class ChangePointMarker(BaseModel):
    """Lightweight marker attached to heatmap cells and trend points."""

    direction: Direction
    change_relative_pct: float | None = None
    transition: Transition | None = None


class ChangePointRead(BaseModel):
    """Full change point detail for list views and detail endpoint."""

    id: uuid.UUID
    asset_id: uuid.UUID
    slo_name: str
    metric_name: str
    period_start: datetime
    period_end: datetime | None = None
    detector: str
    direction: Direction
    change_relative_pct: float | None
    transition: Transition | None = None
    change_absolute: float
    pvalue: float
    pre_segment_mean: float
    post_segment_mean: float
    post_segment_std: float
    status: str
    triage_author: str | None
    triage_note: str | None
    triage_at: datetime | None
    linked_ticket: str | None
    found_by_evaluation_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {'from_attributes': True}


class TriageRequest(StrictInput):
    """Request body for triaging a change point."""

    status: SafeStr
    triage_note: SafeStr | None = None
    linked_ticket: SafeStr | None = None
    triage_author: SafeStr | None = None


class BulkTriageRequest(StrictInput):
    """Request body for bulk-triaging change points."""

    ids: list[uuid.UUID]
    status: SafeStr
    triage_note: SafeStr | None = None
    triage_author: SafeStr | None = None


class ChangePointConfigInput(StrictInput):
    """Optional overrides for change point detection — used in SLO YAML change_point: block."""

    enabled: StrictBool | None = None
    higher_is_better: StrictBool | None = None
    window_size: IntNotBool | None = None
    max_pvalue: FloatNotBool | None = None
    min_magnitude: FloatNotBool | None = None
    min_sample_size: IntNotBool | None = None


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
