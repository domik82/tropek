"""Pydantic schemas for the re-evaluation endpoint."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from tropek.modules.common.schemas import StrictInput

# ---- Discriminated-union scope and selector types (new API) ----


class AssetScope(BaseModel):
    """Scope targeting a single named asset."""

    kind: Literal['asset']
    asset_name: str


class GroupScope(BaseModel):
    """Scope targeting all assets in a named group."""

    kind: Literal['group']
    group_name: str


Scope = Annotated[AssetScope | GroupScope, Field(discriminator='kind')]


class SloSelector(BaseModel):
    """Selector limiting re-evaluation to a single named SLO."""

    kind: Literal['slo']
    slo_name: str


class EvalNamesSelector(BaseModel):
    """Selector limiting re-evaluation to a list of evaluation names."""

    kind: Literal['evaluation_names']
    evaluation_names: list[str] = Field(min_length=1)


Selector = Annotated[SloSelector | EvalNamesSelector, Field(discriminator='kind')]


class ReEvaluateFromDateRequest(StrictInput):
    """Request body for POST /evaluations/re-evaluate/from-date."""

    scope: Scope
    selector: Selector | None = None
    from_date: datetime
    slo_version: int | None = None
    dry_run: bool = False


class ReEvaluateFromBaselineRequest(StrictInput):
    """Request body for POST /evaluations/re-evaluate/from-baseline."""

    scope: Scope
    selector: Selector | None = None
    slo_version: int | None = None
    dry_run: bool = False
    pin_strategy: Literal['skip_to_pin', 'ignore_pin'] | None = None


class ReEvaluateFromEvaluationRequest(StrictInput):
    """Request body for POST /evaluations/re-evaluate/from-evaluation/{evaluation_id}."""

    scope: Scope
    selector: Selector | None = None
    slo_version: int | None = None
    dry_run: bool = False


# ---- Legacy schema (kept for POST /evaluations/re-evaluate) ----


class ReEvaluateRequest(StrictInput):
    """Request body for POST /evaluations/re-evaluate.

    When both ``slo_name`` and ``slo_names`` are omitted, all SLOs assigned
    to the asset are re-evaluated (same resolution logic as POST /evaluate).
    When ``slo_names`` is provided, scoring runs only for the listed SLOs.
    """

    asset_name: str
    slo_name: str | None = None
    slo_names: list[str] | None = None

    # Scope — exactly one required
    from_date: datetime | None = None
    from_baseline: bool = False
    from_evaluation_id: uuid.UUID | None = None

    # Optional
    slo_version: int | None = None
    dry_run: bool = False
    pin_strategy: Literal['skip_to_pin', 'ignore_pin'] | None = None

    @model_validator(mode='after')
    def exactly_one_scope(self) -> ReEvaluateRequest:
        """Ensure exactly one scope parameter is provided."""
        scopes = sum(
            [
                self.from_date is not None,
                self.from_baseline,
                self.from_evaluation_id is not None,
            ]
        )
        if scopes != 1:
            msg = 'exactly one of from_date, from_baseline, or from_evaluation_id is required'
            raise ValueError(msg)
        return self

    @model_validator(mode='after')
    def slo_name_and_names_mutually_exclusive(self) -> ReEvaluateRequest:
        """slo_name and slo_names cannot be supplied together; reject empty lists."""
        if self.slo_name is not None and self.slo_names is not None:
            msg = 'slo_name and slo_names are mutually exclusive'
            raise ValueError(msg)
        if self.slo_names is not None and len(self.slo_names) == 0:
            msg = 'slo_names must be non-empty when provided'
            raise ValueError(msg)
        return self


class ReEvalResultItem(BaseModel):
    """One re-evaluated evaluation in the response."""

    id: uuid.UUID
    evaluation_name: str
    slo_name: str
    slo_version: int
    period_start: datetime
    period_end: datetime
    old_result: str
    new_result: str
    old_score: float
    new_score: float


class ReEvaluateResponse(BaseModel):
    """Response body for POST /evaluations/re-evaluate."""

    affected_evaluations: int
    slo_version_used: int | None
    results: list[ReEvalResultItem]
