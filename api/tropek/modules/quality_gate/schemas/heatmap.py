"""Pydantic schemas for metric heatmap responses."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


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


class HeatmapSummaryCell(BaseModel):
    """Per-column aggregate for an SLO group or the Overall composite row."""

    evaluation_id: uuid.UUID
    period_start: datetime
    result: str
    score: float  # 0-100, achieved_points / total_points x 100
    total_score_pass_threshold: float | None = None
    total_score_warning_threshold: float | None = None
    sli_metadata: dict[str, Any] | None = None
    invalidated: bool = False
    invalidation_note: str | None = None


class HeatmapCellGrouped(BaseModel):
    """A single indicator x column cell in the grouped heatmap."""

    evaluation_id: uuid.UUID  # parent eval (column key)
    slo_evaluation_id: uuid.UUID  # FK to slo_evaluations (for trend navigation)
    period_start: datetime  # display label only
    metric: str
    display_name: str
    result: str
    score: float
    value: float | None = None
    compared_value: float | None = None
    change_relative_pct: float | None = None
    weight: float = 1
    key_sli: bool = False
    pass_targets: list[dict[str, Any]] | None = None
    warning_targets: list[dict[str, Any]] | None = None
    tab_group: str | None = None
    aggregation: str | None = None


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
    has_notes: bool = False


class GroupedMetricHeatmapResponse(BaseModel):
    """Grouped metric heatmap response. Columns are parent EvaluationRun rows."""

    asset_name: str
    columns: list[EvaluationColumn]  # ordered oldest → newest
    groups: list[SloGroup]  # SLO groups in appearance order
    composite: list[HeatmapSummaryCell]  # Overall row (worst-case across all groups)
