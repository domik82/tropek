"""FastAPI routes for asset meta timeline ingestion and read."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from tropek.db.session import get_session
from tropek.modules.asset_meta import service
from tropek.modules.asset_meta.schemas import MetaSnapshotCreate, MetaSnapshotCreated

router = APIRouter(tags=['asset-meta'])


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
