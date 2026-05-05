"""Data access layer for asset meta snapshot tables."""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime
from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tropek.db.models import Asset, AssetMetaClosure, AssetMetaSnapshot, AssetMetaValue


class SnapshotRow(TypedDict):
    """Grouped snapshot with its associated values and closure paths."""

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
