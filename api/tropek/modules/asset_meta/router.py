"""FastAPI routes for asset meta timeline ingestion and read."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from tropek.db.session import get_session
from tropek.modules.asset_meta import service
from tropek.modules.asset_meta.schemas import (
    MetaSnapshotCreate,
    MetaSnapshotCreated,
    TimelineResponse,
    TimelineSummaryResponse,
)
from tropek.modules.common.exceptions import DomainValidationError

router = APIRouter(tags=['asset-meta'])


def _validate_window_params(window_from: datetime, window_to: datetime) -> None:
    """Raise DomainValidationError if the time window is invalid."""
    if window_from >= window_to:
        raise DomainValidationError('from must be before to')


@router.post(
    '/assets/{asset_id}/meta/snapshots',
    status_code=201,
    response_model=MetaSnapshotCreated,
)
async def create_snapshot(
    asset_id: uuid.UUID,
    payload: MetaSnapshotCreate,
    session: AsyncSession = Depends(get_session),
) -> MetaSnapshotCreated:
    """Ingest a point-in-time metadata snapshot for an asset."""
    return await service.create_meta_snapshot(session, asset_id, payload)


@router.get(
    '/assets/{asset_id}/meta/timeline',
    response_model=TimelineResponse,
)
async def get_timeline(
    asset_id: uuid.UUID,
    from_: datetime = Query(..., alias='from'),
    to: datetime = Query(...),
    session: AsyncSession = Depends(get_session),
) -> TimelineResponse:
    """Return the full meta timeline for an asset within a time window."""
    _validate_window_params(from_, to)
    return await service.get_timeline(session, asset_id, window_from=from_, window_to=to)


@router.get(
    '/assets/{asset_id}/meta/timeline/summary',
    response_model=TimelineSummaryResponse,
)
async def get_timeline_summary(
    asset_id: uuid.UUID,
    from_: datetime = Query(..., alias='from'),
    to: datetime = Query(...),
    session: AsyncSession = Depends(get_session),
) -> TimelineSummaryResponse:
    """Return summary stats for the collapsed meta timeline strip."""
    _validate_window_params(from_, to)
    return await service.get_timeline_summary(session, asset_id, window_from=from_, window_to=to)
