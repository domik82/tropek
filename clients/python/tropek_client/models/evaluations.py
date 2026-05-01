"""Evaluation models for TROPEK API."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID

from pydantic import BaseModel

from tropek_client.models.asset_groups import AssetScope
from tropek_client.models.assets import AssetSnapshot

if TYPE_CHECKING:
    from tropek_client.models.annotations import AnnotationRead
    from tropek_client.models.change_points import ChangePointMarker
    from tropek_client.models.slis import SliMetadata


class FailingIndicator(BaseModel):
    """A failing SLI indicator summary."""

    metric: str
    display_name: str
    value: float | int | None
    threshold: str


class PassTarget(BaseModel):
    """A pass or warning target threshold for an indicator."""

    criteria: str
    target_value: float | int
    violated: bool


class IndicatorResult(BaseModel):
    """Full result for a single SLI within an evaluation."""

    metric: str
    display_name: str
    tab_group: str | None = None
    value: float | int | None
    compared_value: float | int | None
    change_absolute: float | int | None
    change_relative_pct: float | int | None
    aggregation: str | None = None
    status: str
    score: float | int
    weight: float | int
    key_sli: bool
    pass_targets: list[PassTarget] | None
    warning_targets: list[PassTarget] | None
    change_point: ChangePointMarker | None = None


class EvaluationSummary(BaseModel):
    """Summary view of a single SLO evaluation result."""

    id: UUID
    evaluation_id: UUID
    evaluation_name: str
    status: str
    result: str | None
    score: float | int | None
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
    original_score: float | int | None = None
    override_reason: str | None = None
    override_author: str | None = None
    asset_snapshot: AssetSnapshot
    variables: dict[str, str]
    annotation_count: int | None = 0
    latest_annotation: AnnotationRead | None = None
    top_failures: list[FailingIndicator] | None = None
    created_at: datetime


class EvaluationDetail(EvaluationSummary):
    """Full evaluation detail including indicator results and annotations."""

    invalidation_note: str | None
    compared_evaluation_ids: list[UUID] | None = None
    annotations: list[AnnotationRead]
    indicator_results: list[IndicatorResult]
    total_score_pass_threshold: float | int | None = None
    total_score_warning_threshold: float | int | None = None
    sli_metadata: dict[str, SliMetadata] | None = None


class GroupScope(BaseModel):
    """Scope targeting all assets within a named group."""

    kind: Literal['group']
    group_name: str


Scope = AssetScope | GroupScope


class SloSelector(BaseModel):
    """Selector that targets evaluations by SLO name."""

    kind: Literal['slo']
    slo_name: str


class EvalNamesSelector(BaseModel):
    """Selector that targets a specific set of evaluation names."""

    kind: Literal['evaluation_names']
    evaluation_names: list[str]


ReEvalSelector = SloSelector | EvalNamesSelector


class BatchPeriod(BaseModel):
    """A single time window within a batch evaluation request."""

    period_start: datetime
    period_end: datetime


class EvaluateSingleRequest(BaseModel):
    """Request body to trigger a single evaluation."""

    asset_name: str
    eval_name: str
    period_start: datetime
    period_end: datetime
    variables: dict[str, Any] | None = None
    compare_to: dict[str, str] | None = None


class EvaluateSingleResponse(BaseModel):
    """Response from a single evaluation trigger."""

    evaluation_id: UUID
    slo_evaluation_ids: list[UUID]


class EvaluateBatchRequest(BaseModel):
    """Request body to trigger a batch evaluation."""

    mode: str
    asset_name: str | None = None
    periods: list[BatchPeriod] | None = None
    asset_names: list[str] | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None
    eval_name: str
    variables: dict[str, Any] | None = None
    compare_to: dict[str, str] | None = None


class EvaluateBatchResponse(BaseModel):
    """Response from a batch evaluation trigger."""

    evaluation_ids: list[UUID]
    slo_evaluation_ids: list[UUID]


class InvalidateRequest(BaseModel):
    """Request body to invalidate an evaluation."""

    invalidation_note: str


class OverrideStatusRequest(BaseModel):
    """Request body to manually override an evaluation result."""

    new_result: str
    reason: str
    author: str


class PinBaselineRequest(BaseModel):
    """Request body to pin an evaluation as the comparison baseline."""

    reason: str
    author: str


class ReEvaluateFromBaselineRequest(BaseModel):
    """Request body to re-evaluate using pinned baselines."""

    scope: Scope
    selector: ReEvalSelector | None = None
    slo_version: int | None = None
    dry_run: bool | None = False
    pin_strategy: str | None = None


class ReEvaluateFromDateRequest(BaseModel):
    """Request body to re-evaluate using a historical date as the baseline reference."""

    scope: Scope
    selector: ReEvalSelector | None = None
    from_date: datetime
    slo_version: int | None = None
    dry_run: bool | None = False
    pin_strategy: str | None = None


class ReEvaluateFromEvaluationRequest(BaseModel):
    """Request body to re-evaluate using a specific evaluation as the baseline."""

    scope: Scope
    selector: ReEvalSelector | None = None
    slo_version: int | None = None
    dry_run: bool | None = False
    pin_strategy: str | None = None


class ReEvaluateResponse(BaseModel):
    """Response from a re-evaluation operation."""

    affected_evaluations: int
    slo_version_used: int | None
    results: list[ReEvalResultItem]


class ReEvalResultItem(BaseModel):
    """Individual result item from a re-evaluation operation."""

    id: UUID
    evaluation_name: str
    slo_name: str
    slo_version: int
    period_start: datetime
    period_end: datetime
    old_result: str
    new_result: str
    old_score: float | int
    new_score: float | int


class TriageRequest(BaseModel):
    """Request body to set triage status on an evaluation."""

    status: str
    triage_note: str | None = None
    linked_ticket: str | None = None
    triage_author: str | None = None


class BulkTriageRequest(BaseModel):
    """Request body to set triage status on multiple evaluations at once."""

    ids: list[UUID]
    status: str
    triage_note: str | None = None
    triage_author: str | None = None


class EvaluationNameEntry(BaseModel):
    """Summary entry for an evaluation name with run count and last run time."""

    name: str
    count: int
    last_run: datetime


class EvaluationColumn(BaseModel):
    """A single column entry in a heatmap evaluation grid."""

    evaluation_id: UUID
    period_start: datetime
    period_end: datetime
    eval_name: str
    has_notes: bool | None = False
