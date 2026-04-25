"""Pydantic schemas for evaluation trigger and batch evaluate endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from tropek.modules.common.schemas import IdentifierKey, SafeStr, StrictInput


class EvaluateSingleRequest(StrictInput):
    """Request body for POST /evaluate."""

    asset_name: SafeStr
    eval_name: SafeStr
    period_start: datetime
    period_end: datetime
    variables: dict[IdentifierKey, SafeStr] = {}
    compare_to: dict[str, str] | None = None


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

    mode: SafeStr  # 'by_date' | 'by_asset'
    asset_name: SafeStr | None = None
    periods: list[BatchPeriod] | None = None
    asset_names: list[SafeStr] | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None
    eval_name: SafeStr
    variables: dict[IdentifierKey, SafeStr] = {}
    compare_to: dict[str, str] | None = None


class EvaluateBatchResponse(BaseModel):
    """Response from POST /evaluate/batch."""

    evaluation_ids: list[uuid.UUID]
    slo_evaluation_ids: list[uuid.UUID]
