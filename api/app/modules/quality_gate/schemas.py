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
    tags: dict[str, Any]
    hidden_at: datetime | None
    hidden_by: str | None
    hidden_reason: str | None
    created_at: datetime
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class AnnotationCreate(BaseModel):
    """Request body for creating an annotation."""

    content: str
    author: str | None = None
    category: str | None = None
    tags: dict[str, Any] = {}


class AnnotationUpdate(BaseModel):
    """Request body for updating an annotation."""

    content: str | None = None
    author: str | None = None
    category: str | None = None
    tags: dict[str, Any] | None = None


class AnnotationHide(BaseModel):
    """Request body for soft-deleting (hiding) an annotation."""

    reason: str
    author: str | None = None


class InvalidateRequest(BaseModel):
    """Request body for invalidating an evaluation."""

    invalidation_note: str


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
    variables: dict[str, Any]
    annotation_count: int = 0
    latest_annotation: AnnotationRead | None = None
    top_failures: list[FailingIndicator] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EvaluationDetail(EvaluationSummary):
    """Full evaluation detail including all annotations and indicator results."""

    invalidation_note: str | None
    compared_evaluation_ids: list[uuid.UUID] = []
    annotations: list[AnnotationRead]
    indicator_results: list[IndicatorResult]
    total_score_pass_threshold: float | None = None
    total_score_warning_threshold: float | None = None
    sli_metadata: dict[str, Any] | None = None

    @model_validator(mode='after')
    def sync_annotation_count(self) -> EvaluationDetail:
        """Keep annotation_count in sync with the annotations list."""
        self.annotation_count = len(self.annotations)
        return self


class TrendPoint(BaseModel):
    """A single point in a metric trend time series."""

    timestamp: datetime
    value: float
    score: float
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
    evaluation_name: str


class MetricHeatmapResponse(BaseModel):
    """Response for the metric heatmap endpoint."""

    asset_name: str
    slots: list[datetime]
    metrics: list[HeatmapMetric]
    cells: list[HeatmapCell]


class EvaluationNameEntry(BaseModel):
    """A distinct evaluation name with usage stats."""

    name: str
    count: int
    last_run: datetime


class TriggerRequest(BaseModel):
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


class AssetTriggerRequest(BaseModel):
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


class BatchTriggerRequest(BaseModel):
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


class EvaluateSingleRequest(BaseModel):
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


class BatchPeriod(BaseModel):
    """A single period window for by_date batch mode."""

    period_start: datetime
    period_end: datetime


class EvaluateBatchRequest(BaseModel):
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


class HeatmapSummaryCell(BaseModel):
    """Per-column aggregate for an SLO group or the Overall composite row."""

    evaluation_id: uuid.UUID
    period_start: datetime
    result: str
    score: float  # 0-100, achieved_points / total_points x 100


class HeatmapCellGrouped(BaseModel):
    """A single indicator x column cell in the grouped heatmap."""

    evaluation_id: uuid.UUID       # parent eval (column key)
    slo_evaluation_id: uuid.UUID   # FK to slo_evaluations (for trend navigation)
    period_start: datetime         # display label only
    metric: str
    display_name: str
    result: str
    score: float


class SloGroup(BaseModel):
    """One SLO's contribution to the grouped heatmap."""

    slo_name: str
    slo_display_name: str | None = None
    metrics: list[HeatmapMetric]
    cells: list[HeatmapCellGrouped]
    summary: list[HeatmapSummaryCell]  # per-column worst-case aggregate


class EvaluationColumn(BaseModel):
    """One heatmap column — corresponds to one parent EvaluationRun."""

    evaluation_id: uuid.UUID
    period_start: datetime
    period_end: datetime
    eval_name: str


class GroupedMetricHeatmapResponse(BaseModel):
    """Grouped metric heatmap response. Columns are parent EvaluationRun rows."""

    asset_name: str
    columns: list[EvaluationColumn]      # ordered oldest → newest
    groups: list[SloGroup]               # SLO groups in appearance order
    composite: list[HeatmapSummaryCell]  # Overall row (worst-case across all groups)
