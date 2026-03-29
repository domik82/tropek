"""Pydantic parameter models for quality gate repository methods."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class EvalCreateParams(BaseModel):
    """Parameters for EvaluationRepository.create_pending()."""

    evaluation_name: str
    period_start: datetime
    period_end: datetime
    ingestion_mode: str
    asset_snapshot: dict[str, object]
    variables: dict[str, object] = Field(default_factory=dict)
    asset_id: uuid.UUID
    slo_name: str
    slo_version: int | None = None
    adapter_used: str | None = None
    sli_name: str | None = None
    sli_version: int | None = None
    data_source_name: str | None = None
