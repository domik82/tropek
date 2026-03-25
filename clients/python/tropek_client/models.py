"""Pydantic models mirroring TROPEK API response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class PagedResponse[T](BaseModel):
    """Generic paginated response."""

    items: list[T]
    total: int


class AssetType(BaseModel):
    """Asset type."""

    id: uuid.UUID
    name: str
    is_default: bool

    model_config = ConfigDict(from_attributes=True)


class Asset(BaseModel):
    """Asset."""

    id: uuid.UUID
    name: str
    display_name: str | None
    type_name: str
    tags: dict[str, str]
    variables: dict[str, str] = {}
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AssetGroupMember(BaseModel):
    """Member of an asset group."""

    asset_id: uuid.UUID
    asset_name: str
    weight: float


class AssetGroupSubgroup(BaseModel):
    """Subgroup reference."""

    group_id: uuid.UUID
    weight: float


class AssetGroup(BaseModel):
    """Asset group with members and subgroups."""

    id: uuid.UUID
    name: str
    display_name: str | None
    members: list[AssetGroupMember]
    subgroups: list[AssetGroupSubgroup]


class AssetGroupTree(BaseModel):
    """Tree of asset groups.

    NOTE: Verify field names against actual GET /asset-groups/tree response.
    If the API returns different field names, update to match.
    """

    top_level: list[AssetGroup]
    all_groups: list[AssetGroup]


class DataSource(BaseModel):
    """Data source registration."""

    id: uuid.UUID
    name: str
    display_name: str | None
    adapter_type: str
    adapter_url: str
    tags: dict[str, Any]
    has_token: bool = False

    model_config = ConfigDict(from_attributes=True)


class SLIDefinition(BaseModel):
    """SLI definition."""

    id: uuid.UUID
    name: str
    display_name: str | None
    version: int
    indicators: dict[str, str]
    notes: str | None
    author: str | None
    tags: dict[str, Any]
    active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SLOObjective(BaseModel):
    """SLO objective in client responses."""

    sli: str
    display_name: str = ""
    pass_criteria: list[str] = []
    warning_criteria: list[str] = []
    weight: int = 1
    key_sli: bool = False
    sort_order: int = 0


class SLODefinition(BaseModel):
    """SLO definition."""

    id: uuid.UUID
    name: str
    display_name: str | None
    version: int
    active: bool
    objectives: list[SLOObjective]
    total_score_pass_pct: float
    total_score_warning_pct: float
    comparison: dict[str, Any]
    notes: str | None
    author: str | None
    tags: dict[str, Any]
    variables: dict[str, Any] = {}
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SLOValidationError(BaseModel):
    """Single validation error."""

    field: str
    message: str


class SLOValidationResult(BaseModel):
    """Result from SLO validation."""

    valid: bool
    errors: list[SLOValidationError]
    objectives: list[dict[str, Any]] | None = None


class BaselineConfig(BaseModel):
    """Baseline configuration for SLO testing."""

    mode: Literal["none", "asset_history", "manual"]
    values: dict[str, float] | None = None


class SLOTestRequest(BaseModel):
    """Request body for POST /slo-definitions/test."""

    slo_yaml: str
    sli_name: str
    data_source_name: str
    asset_name: str
    period_start: datetime
    period_end: datetime
    baseline: BaselineConfig | None = None


class IndicatorResult(BaseModel):
    """Per-SLI evaluation result."""

    metric: str
    display_name: str
    value: float | None
    compared_value: float | None
    change_absolute: float | None
    change_relative_pct: float | None
    status: str
    score: float
    weight: float
    key_sli: bool
    pass_targets: list[dict[str, Any]] | None
    warning_targets: list[dict[str, Any]] | None


class SLOTestResult(BaseModel):
    """Result from SLO test/dry-run."""

    result: str
    score: float
    indicator_results: list[IndicatorResult]
    warning_count: int
    fail_count: int


class FailingIndicator(BaseModel):
    """A failing SLI indicator summary."""

    metric: str
    display_name: str
    value: float | None
    threshold: str


class Annotation(BaseModel):
    """Evaluation annotation."""

    id: uuid.UUID
    content: str
    author: str | None
    category: str | None
    tags: dict[str, Any]
    hidden_at: datetime | None = None
    hidden_by: str | None = None
    hidden_reason: str | None = None
    created_at: datetime
    updated_at: datetime | None


class EvaluationSummary(BaseModel):
    """Compact evaluation for list views."""

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
    override_reason: str | None = None
    override_author: str | None = None
    asset_snapshot: dict[str, Any]
    variables: dict[str, Any]
    annotation_count: int
    latest_annotation: Annotation | None
    top_failures: list[FailingIndicator]
    created_at: datetime


class EvaluationDetail(EvaluationSummary):
    """Full evaluation with annotations and indicator results."""

    invalidation_note: str | None
    compared_evaluation_ids: list[uuid.UUID]
    annotations: list[Annotation]
    indicator_results: list[IndicatorResult]


class TrendPoint(BaseModel):
    """Single trend data point."""

    timestamp: datetime
    value: float
    eval_id: uuid.UUID
    result: str
    baseline: float | None


class AssetSLOLink(BaseModel):
    """Asset-SLO binding."""

    id: uuid.UUID
    link_name: str
    asset_id: uuid.UUID
    slo_name: str
    sli_name: str
    data_source_name: str
    comparison_rules: list[dict[str, Any]] = []


class AssetGroupSLOLink(BaseModel):
    """Asset group-SLO binding."""

    id: uuid.UUID
    link_name: str
    group_id: uuid.UUID
    slo_name: str
    sli_name: str
    data_source_name: str


class SLOBinding(BaseModel):
    """SLO binding (new model — links an SLO to an asset or group via a data source)."""

    id: str
    target_type: str
    target_id: str
    slo_name: str
    data_source_name: str
    comparison_rules: list[dict[str, Any]] | None = None
    source: str = "direct"
    template_binding_id: str | None = None
    created_at: str


class SLOGroup(BaseModel):
    """SLO group response model."""

    id: str
    name: str
    display_name: str | None
    template_slo_name: str
    template_slo_version: int
    gen_variables: dict[str, list[str]]
    tags: dict[str, Any]
    author: str | None
    version: int
    active: bool
    generated_slo_count: int


class TemplateBinding(BaseModel):
    """Template binding response model."""

    id: str
    target_type: str
    target_id: str
    template_group_name: str
    data_source_name: str
    created_at: str
