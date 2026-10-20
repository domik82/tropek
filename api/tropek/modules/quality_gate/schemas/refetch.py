"""Pydantic schemas for refetching stored SLO evaluations from the source."""

from __future__ import annotations

import uuid
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, Field

from tropek.modules.common.schemas import SafeStr, StrictInput

Reason = Annotated[SafeStr, Field(max_length=500)]
RequestedBy = Annotated[SafeStr, Field(max_length=120)]


class RefetchRequest(StrictInput):
    """Request body for POST /evaluations/refetch.

    ``from`` and ``to`` are inclusive on ``period_start`` and must carry a UTC offset.
    """

    asset_name: SafeStr
    from_: AwareDatetime = Field(alias='from')
    to: AwareDatetime
    evaluation_name: SafeStr | None = None
    slo_names: list[SafeStr] | None = None
    only_failed: bool = False
    dry_run: bool = False
    reason: Reason | None = None
    requested_by: RequestedBy | None = None


class RefetchRunRequest(StrictInput):
    """Request body for POST /evaluation-run/{run_id}/refetch."""

    only_failed: bool = False
    dry_run: bool = False
    reason: Reason | None = None
    requested_by: RequestedBy | None = None


class RefetchSkipped(BaseModel):
    """A matched SLO evaluation that refetch left untouched."""

    evaluation_id: uuid.UUID
    slo_name: str
    reason: str


class RefetchResponse(BaseModel):
    """Response body for both refetch endpoints."""

    matched: int
    refetched: int
    skipped: list[RefetchSkipped]
    run_ids: list[uuid.UUID]
    dry_run: bool
