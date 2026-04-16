"""Service layer for asset meta snapshot ingest."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from tropek.modules.asset_meta.repositories import AssetMetaRepository
from tropek.modules.asset_meta.schemas import MetaSnapshotCreate, MetaSnapshotCreated
from tropek.modules.common.exceptions import DomainValidationError, NotFoundError

logger = logging.getLogger(__name__)


async def create_meta_snapshot(
    session: AsyncSession,
    asset_id: UUID,
    payload: MetaSnapshotCreate,
) -> MetaSnapshotCreated:
    """Ingest one snapshot. Thin orchestrator over validation + existence + write."""
    _validate_payload_has_content(payload)
    repository = AssetMetaRepository(session)
    await _ensure_asset_exists(repository, asset_id)
    snapshot_id = await _write_snapshot_rows(repository, asset_id, payload)
    await session.commit()
    return MetaSnapshotCreated(snapshot_id=snapshot_id)


def _validate_payload_has_content(payload: MetaSnapshotCreate) -> None:
    """Reject snapshots with neither values nor closures."""
    if not payload.values and not payload.closed:
        raise DomainValidationError('snapshot must contain values or closed')


async def _ensure_asset_exists(repository: AssetMetaRepository, asset_id: UUID) -> None:
    """Raise NotFoundError if the asset does not exist."""
    if not await repository.asset_exists(asset_id):
        raise NotFoundError('asset', str(asset_id))


async def _write_snapshot_rows(
    repository: AssetMetaRepository,
    asset_id: UUID,
    payload: MetaSnapshotCreate,
) -> UUID:
    """Insert the snapshot + values + closures rows. Does not commit."""
    snapshot = await repository.insert_snapshot(
        asset_id=asset_id,
        source=payload.source,
        observed_at=payload.observed_at,
    )
    if payload.values:
        value_entries = [(entry.path, entry.value) for entry in payload.values]
        await repository.insert_values(snapshot.id, value_entries)
    if payload.closed:
        closure_entries = [entry.path for entry in payload.closed]
        await repository.insert_closures(snapshot.id, closure_entries)
    return snapshot.id
