"""Pydantic parameter models for quality gate repository methods."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.common.schemas import StrictInput

from app.db.models import SLOObjective
from app.modules.quality_gate.engine.result_models import IndicatorResult


class EvalCreateParams(StrictInput):
    """Parameters for EvaluationRepository.create_pending()."""

    evaluation_id: uuid.UUID
    evaluation_name: str
    period_start: datetime
    period_end: datetime
    ingestion_mode: str
    asset_snapshot: dict[str, object]
    variables: dict[str, str] = Field(default_factory=dict)
    asset_id: uuid.UUID
    slo_name: str
    slo_version: int | None = None
    adapter_used: str | None = None
    sli_name: str | None = None
    sli_version: int | None = None
    data_source_name: str | None = None
    slo_definition_id: uuid.UUID | None = None
    sli_definition_id: uuid.UUID | None = None


class ReEvalUpdateParams(StrictInput):
    """Parameters for BaselineRepository.update_reeval_result()."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    eval_id: uuid.UUID
    new_result: str
    new_score: float
    new_engine_results: list[IndicatorResult] | None = None
    slo_objectives: list[SLOObjective] | None = None
    old_result: str
    old_score: float
    slo_version: int | None = None
