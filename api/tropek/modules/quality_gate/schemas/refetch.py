"""Pydantic schemas for refetching stored SLO evaluations from the source."""

from __future__ import annotations

import uuid
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, Field

from tropek.modules.common.schemas import SafeStr, StrictInput

RefetchReason = Annotated[SafeStr, Field(max_length=500)]
RefetchRequester = Annotated[SafeStr, Field(max_length=120)]


class RefetchRequest(StrictInput):
    """Request body for POST /evaluations/refetch.

    ``from`` and ``to`` are inclusive on ``period_start`` and must carry a UTC offset.
    """

    asset_name: SafeStr
    from_: AwareDatetime = Field(alias='from')
    to: AwareDatetime
    evaluation_name: SafeStr
    slo_names: list[SafeStr] | None = Field(default=None, max_length=200)
    only_failed: bool = False
    dry_run: bool = False
    reason: RefetchReason | None = None
    requested_by: RefetchRequester | None = None


class RefetchRunRequest(StrictInput):
    """Request body for POST /evaluation-run/{run_id}/refetch."""

    only_failed: bool = False
    dry_run: bool = False
    reason: RefetchReason | None = None
    requested_by: RefetchRequester | None = None


class RefetchResponse(BaseModel):
    """Response body for both refetch endpoints."""

    matched: int
    refetched: int
    run_ids: list[uuid.UUID]
    dry_run: bool
