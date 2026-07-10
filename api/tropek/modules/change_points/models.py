"""Internal worker DTOs for the change point detection step.

These are worker-internal value objects (some hold ORM rows and repository
types via ``arbitrary_types_allowed``) and are deliberately kept out of
``schemas.py``, which defines the API/UI-facing contract.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from tropek.modules.change_points.detector import ChangePointResult
from tropek.modules.change_points.repository import ResolvedConfig


class MetricSeries(BaseModel):
    """Time-ordered metric values extracted from evaluation history."""

    values: list[float]
    timestamps: list[datetime]
    period_ends: list[datetime | None]
    evaluation_run_ids: list[uuid.UUID]


class EnabledObjective(BaseModel):
    """An enabled objective and its resolved change-point config for this run."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    metric_name: str
    resolved: ResolvedConfig
    indicator_result_id: uuid.UUID


class ChangePointInputs(BaseModel):
    """Everything the compute phase needs, loaded in a single read session."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    comparison_name: str
    enabled_objectives: list[EnabledObjective]
    shared_history: list[Any]  # SLOEvaluation ORM rows, ordered period_start DESC


class DetectedBatch(BaseModel):
    """Detections for one objective, ready to persist."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    metric_name: str
    indicator_result_id: uuid.UUID
    series: MetricSeries
    detected: list[ChangePointResult]
