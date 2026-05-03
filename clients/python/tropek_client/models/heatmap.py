"""Heatmap response models for the navigator view."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from tropek_client.models.evaluations import EvaluationColumn, PassTarget

if TYPE_CHECKING:
    from tropek_client.models.change_points import ChangePointMarker
    from tropek_client.models.slis import SliMetadata


class HeatmapMetric(BaseModel):
    """A metric entry in a heatmap."""

    name: str
    display_name: str


class HeatmapCell(BaseModel):
    """A single cell in a flat heatmap."""

    slot: datetime
    metric: str
    display_name: str
    result: str
    score: float | int
    eval_id: UUID
    evaluation_name: str


class HeatmapCellGrouped(BaseModel):
    """A cell in a grouped heatmap with full SLI detail."""

    evaluation_id: UUID
    slo_evaluation_id: UUID
    period_start: datetime
    metric: str
    display_name: str
    result: str
    score: float | int
    value: float | int | None = None
    compared_value: float | int | None = None
    change_absolute: float | int | None = None
    change_relative_pct: float | int | None = None
    weight: float | int = 1
    key_sli: bool = False
    pass_targets: list[PassTarget] | None = None
    warning_targets: list[PassTarget] | None = None
    tab_group: str | None = None
    aggregation: str | None = None
    change_point: ChangePointMarker | None = None


class HeatmapSummaryCell(BaseModel):
    """A summary cell representing a full evaluation run in a heatmap."""

    evaluation_id: UUID
    period_start: datetime
    result: str
    score: float | int
    total_score_pass_threshold: float | int | None = None
    total_score_warning_threshold: float | int | None = None
    sli_metadata: dict[str, SliMetadata] | None = None
    slo_version: int | None = None
    sli_version: int | None = None
    invalidated: bool = False
    invalidation_note: str | None = None


class HeatmapSloGroupSection(BaseModel):
    """A grouped section of heatmap cells for one SLO."""

    slo_name: str
    slo_display_name: str | None = None
    metrics: list[HeatmapMetric]
    cells: list[HeatmapCellGrouped]
    summary: list[HeatmapSummaryCell]


class GroupedMetricHeatmapResponse(BaseModel):
    """Response containing a grouped metric heatmap."""

    asset_name: str
    columns: list[EvaluationColumn]
    groups: list[HeatmapSloGroupSection]
    composite: list[HeatmapSummaryCell]


class MetricHeatmapResponse(BaseModel):
    """Response containing a flat metric heatmap."""

    asset_name: str
    slots: list[datetime]
    metrics: list[HeatmapMetric]
    cells: list[HeatmapCell]
