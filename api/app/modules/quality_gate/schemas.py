"""Pydantic schemas for evaluation list, detail, annotations, and trend."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator


class FailingIndicator(BaseModel):
    """A single failing SLI indicator summary."""

    metric: str
    display_name: str
    value: float | None
    threshold: str


class AnnotationRead(BaseModel):
    """Response schema for an evaluation annotation."""

    id: uuid.UUID
    content: str
    author: str | None
    category: str | None
    meta: dict[str, Any]
    created_at: datetime
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class AnnotationCreate(BaseModel):
    """Request body for creating an annotation."""

    content: str
    author: str | None = None
    category: str | None = None
    meta: dict[str, Any] = {}


class AnnotationUpdate(BaseModel):
    """Request body for updating an annotation."""

    content: str | None = None
    author: str | None = None
    category: str | None = None
    meta: dict[str, Any] | None = None


class InvalidateRequest(BaseModel):
    """Request body for invalidating an evaluation."""

    invalidation_note: str
    author: str


class IndicatorResult(BaseModel):
    """A single SLI indicator evaluation result."""

    metric: str
    display_name: str
    tab_group: str | None = None
    value: float | None
    compared_value: float | None
    change_absolute: float | None
    change_relative_pct: float | None
    aggregation: str | None = None
    status: str
    score: float
    weight: float
    key_sli: bool
    pass_targets: list[dict[str, Any]] | None
    warning_targets: list[dict[str, Any]] | None


class EvaluationSummary(BaseModel):
    """Compact evaluation row for list views."""

    id: uuid.UUID
    evaluation_name: str
    status: str
    result: str | None
    score: float | None
    period_start: datetime
    period_end: datetime
    slo_name: str | None
    slo_version: int | None
    sli_name: str | None
    sli_version: int | None
    data_source_name: str | None
    ingestion_mode: str
    adapter_used: str | None
    invalidated: bool
    baseline_pinned_at: datetime | None = None
    baseline_unpinned_at: datetime | None = None
    baseline_pin_reason: str | None = None
    baseline_pin_author: str | None = None
    original_result: str | None = None
    original_score: float | None = None
    override_reason: str | None = None
    override_author: str | None = None
    asset_snapshot: dict[str, Any]
    evaluation_metadata: dict[str, Any]
    annotation_count: int = 0
    latest_annotation: AnnotationRead | None = None
    top_failures: list[FailingIndicator] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EvaluationDetail(EvaluationSummary):
    """Full evaluation detail including all annotations and indicator results."""

    invalidation_note: str | None
    invalidation_author: str | None
    compared_evaluation_ids: list[uuid.UUID] = []
    annotations: list[AnnotationRead]
    indicator_results: list[IndicatorResult]

    @model_validator(mode="after")
    def sync_annotation_count(self) -> EvaluationDetail:
        """Keep annotation_count in sync with the annotations list."""
        self.annotation_count = len(self.annotations)
        return self


class TrendPoint(BaseModel):
    """A single point in a metric trend time series."""

    timestamp: datetime
    value: float
    eval_id: uuid.UUID
    result: str
    baseline: float | None


class PinBaselineRequest(BaseModel):
    """Request body for pinning an evaluation as baseline."""

    reason: str
    author: str


class OverrideStatusRequest(BaseModel):
    """Request body for overriding evaluation result."""

    new_result: str
    reason: str
    author: str


class HeatmapMetric(BaseModel):
    """A metric definition in the heatmap grid."""

    name: str
    display_name: str


class HeatmapCell(BaseModel):
    """A single cell in the metric heatmap grid."""

    slot: datetime
    metric: str
    display_name: str
    result: str
    score: float
    eval_id: uuid.UUID


class MetricHeatmapResponse(BaseModel):
    """Response for the metric heatmap endpoint."""

    asset_name: str
    slots: list[datetime]
    metrics: list[HeatmapMetric]
    cells: list[HeatmapCell]


class TriggerRequest(BaseModel):
    """Request body for triggering a single evaluation."""

    asset_name: str
    evaluation_name: str
    slo_name: str
    period_start: datetime
    period_end: datetime
    metadata: dict[str, str] = {}


class TriggerResponse(BaseModel):
    """Response from evaluation trigger."""

    id: uuid.UUID
    status: str


class BatchTriggerRequest(BaseModel):
    """Request body for triggering a group evaluation batch."""

    group_name: str
    evaluation_name: str
    period_start: datetime
    period_end: datetime
    metadata: dict[str, str] = {}


class BatchTriggerResponse(BaseModel):
    """Response from batch trigger."""

    batch_id: uuid.UUID
    evaluation_ids: list[uuid.UUID]
    status: str
