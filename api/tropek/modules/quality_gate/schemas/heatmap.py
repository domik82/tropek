"""Pydantic schemas for metric heatmap responses."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from tropek.modules.change_points.schemas import ChangePointMarker
from tropek.modules.quality_gate.schemas.evaluations import PassTarget, SliMetadata


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
    sli_metadata: dict[str, SliMetadata] | None = None
    slo_version: int | None = None
    sli_version: int | None = None
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
    pass_targets: list[PassTarget] | None = None
    warning_targets: list[PassTarget] | None = None
    tab_group: str | None = None
    aggregation: str | None = None
    change_point: ChangePointMarker | None = None


class HeatmapSloGroupSection(BaseModel):
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
    groups: list[HeatmapSloGroupSection]  # SLO groups in appearance order
    composite: list[HeatmapSummaryCell]  # Overall row (worst-case across all groups)


class HeatmapColumnSloFragment(BaseModel):
    """One SLO's contribution to one column's fragment.

    Criteria strings are embedded inside each cell's pass_targets/warning_targets
    and are correctly scoped to the SLO version that ran at that moment — a
    later SLO version edit does not mutate this fragment.
    """

    slo_name: str
    slo_display_name: str | None = None
    metrics: list[HeatmapMetric]
    cells: list[HeatmapCellGrouped]
    summary: HeatmapSummaryCell  # this SLO's per-column summary cell


class HeatmapColumnFragment(BaseModel):
    """One column of the grouped heatmap, cached independently in Redis.

    Cache key: `heatmap:col:v1:{evaluation_run_id}` with a 7-day TTL backstop.
    The full GroupedMetricHeatmapResponse is assembled by merging N fragments
    at read time — see heatmap_cache.assemble_response().
    """

    schema_version: int = 1  # bumped when the fragment shape changes
    evaluation_run_id: uuid.UUID
    column: EvaluationColumn
    per_slo: list[HeatmapColumnSloFragment]
    composite_summary: HeatmapSummaryCell
