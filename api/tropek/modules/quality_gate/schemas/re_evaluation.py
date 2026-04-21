"""Pydantic schemas for the re-evaluation endpoint."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from tropek.modules.common.schemas import SafeStr, StrictInput

# ---- Discriminated-union scope and selector types (new API) ----


class AssetScope(BaseModel):
    """Scope targeting a single named asset."""

    kind: Literal['asset']
    asset_name: SafeStr


class GroupScope(BaseModel):
    """Scope targeting all assets in a named group."""

    kind: Literal['group']
    group_name: SafeStr


Scope = Annotated[AssetScope | GroupScope, Field(discriminator='kind')]


class SloSelector(BaseModel):
    """Selector limiting re-evaluation to a single named SLO."""

    kind: Literal['slo']
    slo_name: SafeStr


class EvalNamesSelector(BaseModel):
    """Selector limiting re-evaluation to a list of evaluation names."""

    kind: Literal['evaluation_names']
    evaluation_names: list[SafeStr] = Field(min_length=1)


Selector = Annotated[SloSelector | EvalNamesSelector, Field(discriminator='kind')]


class ReEvaluateFromDateRequest(StrictInput):
    """Request body for POST /evaluations/re-evaluate/from-date."""

    scope: Scope
    selector: Selector | None = None
    from_date: datetime
    slo_version: int | None = None
    dry_run: bool = False
    pin_strategy: Literal['skip_to_pin', 'ignore_pin'] | None = None


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


# ---- Internal service type (not exposed via API) ----


class ReEvaluateRequest(BaseModel):
    """Internal parameter object used by re_evaluation_service bridges.

    Not exposed via any API route. The public split endpoints
    (ReEvaluateFrom*Request) are the API surface; bridge functions
    translate them into this type before calling the core service.
    """

    asset_name: str
    slo_name: str | None = None
    slo_names: list[str] | None = None

    from_date: datetime | None = None
    from_baseline: bool = False
    from_evaluation_id: uuid.UUID | None = None

    slo_version: int | None = None
    dry_run: bool = False
    pin_strategy: Literal['skip_to_pin', 'ignore_pin'] | None = None


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
