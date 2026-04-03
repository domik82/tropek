"""Pydantic schemas for evaluation trigger and batch evaluate endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.modules.common.schemas import StrictInput


class TriggerRequest(StrictInput):
    """Request body for triggering a single evaluation."""

    asset_name: str
    evaluation_name: str
    slo_name: str
    period_start: datetime
    period_end: datetime
    variables: dict[str, str] = {}


class TriggerResponse(BaseModel):
    """Response from evaluation trigger."""

    id: uuid.UUID
    status: str


class AssetTriggerRequest(StrictInput):
    """Request body for triggering all SLOs for an asset."""

    asset_name: str
    evaluation_name: str
    period_start: datetime
    period_end: datetime
    variables: dict[str, str] = {}


class AssetTriggerResponse(BaseModel):
    """Response from asset-level trigger."""

    evaluation_ids: list[uuid.UUID]
    slo_names: list[str]
    status: str


class BatchTriggerRequest(StrictInput):
    """Request body for triggering a group evaluation batch."""

    group_name: str
    evaluation_name: str
    period_start: datetime
    period_end: datetime
    variables: dict[str, str] = {}


class BatchConflict(BaseModel):
    """A single conflicting item in a batch trigger."""

    asset_name: str
    slo_name: str
    evaluation_name: str
    period_start: datetime
    period_end: datetime
    existing_status: str


class BatchTriggerResponse(BaseModel):
    """Response from batch trigger."""

    batch_id: uuid.UUID
    evaluation_ids: list[uuid.UUID]
    status: str


class EvaluateSingleRequest(StrictInput):
    """Request body for POST /evaluate."""

    asset_name: str
    eval_name: str
    period_start: datetime
    period_end: datetime
    variables: dict[str, str] = {}


class EvaluateSingleResponse(BaseModel):
    """Response from POST /evaluate."""

    evaluation_id: uuid.UUID
    slo_evaluation_ids: list[uuid.UUID]


class BatchPeriod(StrictInput):
    """A single period window for by_date batch mode."""

    period_start: datetime
    period_end: datetime


class EvaluateBatchRequest(StrictInput):
    """Request body for POST /evaluate/batch.

    mode='by_date': same asset, multiple time windows (asset_name + periods required)
    mode='by_asset': same window, multiple assets (asset_names + period_start/end required)
    """

    mode: str  # 'by_date' | 'by_asset'
    asset_name: str | None = None
    periods: list[BatchPeriod] | None = None
    asset_names: list[str] | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None
    eval_name: str
    variables: dict[str, str] = {}


class EvaluateBatchResponse(BaseModel):
    """Response from POST /evaluate/batch."""

    evaluation_ids: list[uuid.UUID]
    slo_evaluation_ids: list[uuid.UUID]
