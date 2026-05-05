"""Data access layer for asset meta snapshot tables."""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime
from typing import TypedDict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tropek.db.models import Asset, AssetMetaClosure, AssetMetaSnapshot, AssetMetaValue


class SnapshotRow(TypedDict):
    """Grouped snapshot with its associated values and closure label paths."""

    source: str
    observed_at: datetime
    values: list[tuple[list[str], str]]
    closures: list[list[str]]


class AssetMetaRepository:
    """Data access for asset_meta_snapshots, asset_meta_values, and asset_meta_closures."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert_snapshot(self, asset_id: uuid.UUID, source: str, observed_at: datetime) -> AssetMetaSnapshot:
        """Insert one snapshot row and return it.

        Args:
            asset_id: UUID of the asset this snapshot belongs to.
            source: Identifier for the system that pushed this snapshot.
            observed_at: Timestamp of when the metadata was observed (not when it was stored).

        Returns:
            The newly created AssetMetaSnapshot record.
        """
        snapshot = AssetMetaSnapshot(
            id=uuid.uuid4(),
            asset_id=asset_id,
            source=source,
            observed_at=observed_at,
        )
        self._session.add(snapshot)
        await self._session.flush()
        return snapshot

    async def insert_values(self, snapshot_id: uuid.UUID, entries: Sequence[tuple[list[str], str]]) -> None:
        """Bulk insert key-value leaf rows for a snapshot.

        Args:
            snapshot_id: UUID of the parent snapshot.
            entries: Sequence of (label_path, value) tuples where label_path is a list of hierarchy segments.
        """
        value_rows = [
            AssetMetaValue(snapshot_id=snapshot_id, label_path=label_path, value=value) for label_path, value in entries
        ]
        self._session.add_all(value_rows)

    async def insert_closures(self, snapshot_id: uuid.UUID, entries: Sequence[list[str]]) -> None:
        """Bulk insert closure-table rows for a snapshot.

        Args:
            snapshot_id: UUID of the parent snapshot.
            entries: Sequence of label_paths, each label_path being a list of hierarchy segments.
        """
        closure_rows = [AssetMetaClosure(snapshot_id=snapshot_id, label_path=label_path) for label_path in entries]
        self._session.add_all(closure_rows)

    async def load_snapshots_for_derivation(self, asset_id: uuid.UUID, until: datetime) -> list[SnapshotRow]:
        """Load all snapshots up to `until`, with their values and closures, grouped in Python.

        Args:
            asset_id: UUID of the asset whose snapshots to load.
            until: Upper bound (inclusive) on observed_at.

        Returns:
            SnapshotRow dicts ordered by observed_at ASC, id ASC.
        """
        snapshot_query = (
            select(AssetMetaSnapshot)
            .where(AssetMetaSnapshot.asset_id == asset_id)
            .where(AssetMetaSnapshot.observed_at <= until)
            .order_by(AssetMetaSnapshot.observed_at.asc(), AssetMetaSnapshot.id.asc())
        )
        snapshot_result = await self._session.execute(snapshot_query)
        snapshots = list(snapshot_result.scalars().all())

        if not snapshots:
            return []

        snapshot_ids = [snapshot.id for snapshot in snapshots]

        values_query = select(AssetMetaValue).where(AssetMetaValue.snapshot_id.in_(snapshot_ids))
        values_result = await self._session.execute(values_query)
        all_values = list(values_result.scalars().all())

        closures_query = select(AssetMetaClosure).where(AssetMetaClosure.snapshot_id.in_(snapshot_ids))
        closures_result = await self._session.execute(closures_query)
        all_closures = list(closures_result.scalars().all())

        values_by_snapshot: dict[uuid.UUID, list[tuple[list[str], str]]] = defaultdict(list)
        for value_row in all_values:
            values_by_snapshot[value_row.snapshot_id].append((value_row.label_path, value_row.value))

        closures_by_snapshot: dict[uuid.UUID, list[list[str]]] = defaultdict(list)
        for closure_row in all_closures:
            closures_by_snapshot[closure_row.snapshot_id].append(closure_row.label_path)

        return [
            SnapshotRow(
                source=snapshot.source,
                observed_at=snapshot.observed_at,
                values=values_by_snapshot.get(snapshot.id, []),
                closures=closures_by_snapshot.get(snapshot.id, []),
            )
            for snapshot in snapshots
        ]

    async def list_snapshots(
        self,
        asset_id: uuid.UUID,
        *,
        source: str | None = None,
        observed_from: datetime | None = None,
        observed_to: datetime | None = None,
    ) -> list[AssetMetaSnapshot]:
        """Return snapshots for an asset, newest first, with optional filters."""
        query = (
            select(AssetMetaSnapshot)
            .where(AssetMetaSnapshot.asset_id == asset_id)
            .order_by(AssetMetaSnapshot.observed_at.desc())
        )
        if source is not None:
            query = query.where(AssetMetaSnapshot.source == source)
        if observed_from is not None:
            query = query.where(AssetMetaSnapshot.observed_at >= observed_from)
        if observed_to is not None:
            query = query.where(AssetMetaSnapshot.observed_at <= observed_to)
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def get_snapshot(self, asset_id: uuid.UUID, snapshot_id: uuid.UUID) -> AssetMetaSnapshot | None:
        """Return a single snapshot by ID, scoped to the given asset, or None if not found."""
        query = (
            select(AssetMetaSnapshot)
            .where(AssetMetaSnapshot.id == snapshot_id)
            .where(AssetMetaSnapshot.asset_id == asset_id)
        )
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def get_snapshot_values(self, snapshot_id: uuid.UUID) -> list[AssetMetaValue]:
        """Return all value rows belonging to a snapshot."""
        query = select(AssetMetaValue).where(AssetMetaValue.snapshot_id == snapshot_id)
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def get_snapshot_closures(self, snapshot_id: uuid.UUID) -> list[AssetMetaClosure]:
        """Return all closure rows belonging to a snapshot."""
        query = select(AssetMetaClosure).where(AssetMetaClosure.snapshot_id == snapshot_id)
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def delete_snapshot(self, asset_id: uuid.UUID, snapshot_id: uuid.UUID) -> bool:
        """Delete a snapshot scoped to the given asset. Returns True if deleted, False if not found."""
        snapshot = await self.get_snapshot(asset_id, snapshot_id)
        if snapshot is None:
            return False
        await self._session.delete(snapshot)
        await self._session.flush()
        return True

    async def count_values_and_closures(self, snapshot_ids: list[uuid.UUID]) -> dict[uuid.UUID, tuple[int, int]]:
        """Return a mapping of snapshot_id to (value_count, closure_count) for the given IDs."""
        if not snapshot_ids:
            return {}

        value_counts_query = (
            select(AssetMetaValue.snapshot_id, func.count())
            .where(AssetMetaValue.snapshot_id.in_(snapshot_ids))
            .group_by(AssetMetaValue.snapshot_id)
        )
        value_result = await self._session.execute(value_counts_query)
        value_counts: dict[uuid.UUID, int] = {row[0]: row[1] for row in value_result.all()}

        closure_counts_query = (
            select(AssetMetaClosure.snapshot_id, func.count())
            .where(AssetMetaClosure.snapshot_id.in_(snapshot_ids))
            .group_by(AssetMetaClosure.snapshot_id)
        )
        closure_result = await self._session.execute(closure_counts_query)
        closure_counts: dict[uuid.UUID, int] = {row[0]: row[1] for row in closure_result.all()}

        return {sid: (value_counts.get(sid, 0), closure_counts.get(sid, 0)) for sid in snapshot_ids}

    async def asset_exists(self, asset_id: uuid.UUID) -> bool:
        """Check whether an asset with the given ID exists.

        Args:
            asset_id: UUID to look up.

        Returns:
            True if the asset exists, False otherwise.
        """
        existence_query = select(Asset.id).where(Asset.id == asset_id).limit(1)
        existence_result = await self._session.execute(existence_query)
        return existence_result.scalar_one_or_none() is not None
