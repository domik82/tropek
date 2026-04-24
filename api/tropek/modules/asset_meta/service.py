"""Service layer for asset meta snapshot ingest and timeline reads."""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from tropek.modules.asset_meta.repositories import AssetMetaRepository
from tropek.modules.asset_meta.schemas import (
    MetaSnapshotCreate,
    MetaSnapshotCreated,
    TimelineResponse,
    TimelineSummaryResponse,
)
from tropek.modules.asset_meta.timeline import (
    SnapshotWithEntries,
    build_timeline_response,
    count_distinct_leaf_paths,
)
from tropek.modules.asset_meta.timeline.clipping import clip_spans
from tropek.modules.asset_meta.timeline.conflict_resolution import resolve_multi_source_conflicts
from tropek.modules.asset_meta.timeline.derivation import derive_raw_spans
from tropek.modules.common.exceptions import NotFoundError

logger = logging.getLogger(__name__)


async def create_meta_snapshot(
    session: AsyncSession,
    asset_id: UUID,
    payload: MetaSnapshotCreate,
) -> MetaSnapshotCreated:
    """Ingest one snapshot. Thin orchestrator over existence check + write."""
    repository = AssetMetaRepository(session)
    await _ensure_asset_exists(repository, asset_id)
    snapshot_id = await _write_snapshot_rows(repository, asset_id, payload)
    await session.commit()
    return MetaSnapshotCreated(snapshot_id=snapshot_id)


async def get_timeline(
    session: AsyncSession,
    asset_id: UUID,
    window_from: datetime,
    window_to: datetime,
) -> TimelineResponse:
    """Read one asset's timeline. Thin orchestrator over load + derive."""
    repository = AssetMetaRepository(session)
    await _ensure_asset_exists(repository, asset_id)
    snapshot_rows = await repository.load_snapshots_for_derivation(
        asset_id=asset_id,
        until=window_to,
    )
    snapshots = [
        SnapshotWithEntries(
            source=row['source'],
            observed_at=row['observed_at'],
            values=row['values'],
            closures=row['closures'],
        )
        for row in snapshot_rows
    ]
    wire = build_timeline_response(
        asset_id=asset_id,
        snapshots=snapshots,
        window_from=window_from,
        window_to=window_to,
        logger=logger,
    )
    return TimelineResponse.model_validate(wire)


async def get_timeline_summary(
    session: AsyncSession,
    asset_id: UUID,
    window_from: datetime,
    window_to: datetime,
) -> TimelineSummaryResponse:
    """Return just the item count for the collapsed strip."""
    repository = AssetMetaRepository(session)
    await _ensure_asset_exists(repository, asset_id)
    snapshot_rows = await repository.load_snapshots_for_derivation(
        asset_id=asset_id,
        until=window_to,
    )
    snapshots = [
        SnapshotWithEntries(
            source=row['source'],
            observed_at=row['observed_at'],
            values=row['values'],
            closures=row['closures'],
        )
        for row in snapshot_rows
    ]
    raw_spans = derive_raw_spans(snapshots)
    resolved = resolve_multi_source_conflicts(raw_spans, asset_id, logger)
    clipped = clip_spans(resolved, window_from, window_to)
    item_count = count_distinct_leaf_paths(clipped)
    return TimelineSummaryResponse.model_validate({'itemCount': item_count})


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
