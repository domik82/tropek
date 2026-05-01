"""Pydantic schemas for evaluation summary, detail, and indicator results."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tropek.modules.change_points.schemas import ChangePointMarker
from tropek.modules.quality_gate.schemas.annotations import AnnotationRead


class AssetSnapshot(BaseModel):
    """Snapshot of asset identity/version at evaluation time."""

    asset_id: str | None = None
    name: str
    display_name: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)
    primary_version: str | None = None
    build_ref: str | None = None


class SliMetadata(BaseModel):
    """Per-metric aggregation fidelity info for a single indicator."""

    mode: Literal['aggregated']
    expected_samples: int
    actual_samples: int
    missing_pct: float
    chunks_failed: int


class PassTarget(BaseModel):
    """A single resolved pass/warning target on an indicator result."""

    criteria: str
    target_value: float
    violated: bool


class FailingIndicator(BaseModel):
    """A single failing SLI indicator summary."""

    metric: str
    display_name: str
    value: float | None
    threshold: str


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
    pass_targets: list[PassTarget] | None
    warning_targets: list[PassTarget] | None
    change_point: ChangePointMarker | None = None


class EvaluationSummary(BaseModel):
    """Compact evaluation row for list views."""

    id: uuid.UUID
    evaluation_id: uuid.UUID
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
    asset_snapshot: AssetSnapshot
    variables: dict[str, str]
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
    sli_metadata: dict[str, SliMetadata] | None = None

    @model_validator(mode='after')
    def sync_annotation_count(self) -> EvaluationDetail:
        """Keep annotation_count in sync with the annotations list."""
        self.annotation_count = len(self.annotations)
        return self


class EvaluationNameEntry(BaseModel):
    """A distinct evaluation name with usage stats."""

    name: str
    count: int
    last_run: datetime


class TrendTargetEntry(BaseModel):
    """A single resolved criteria target within a trend point."""

    criteria: str
    target_value: float
    violated: bool


class TrendTargets(BaseModel):
    """Pass and warn target lists for a trend point."""

    pass_targets: list[TrendTargetEntry] | None = Field(default=None, alias='pass')
    warn: list[TrendTargetEntry] | None = None

    model_config = {'populate_by_name': True}


class TrendPoint(BaseModel):
    """A single point in a metric trend time series."""

    timestamp: datetime
    value: float
    score: float
    eval_id: uuid.UUID
    result: str
    baseline: float | None
    evaluation_name: str | None = None
    targets: TrendTargets | None = None
    change_point: ChangePointMarker | None = None
