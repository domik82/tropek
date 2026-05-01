"""Integration tests for AssetMetaRepository.

Requires TEST_DATABASE_URL and a running TimescaleDB instance.
Run: ./scripts/api-test.sh --tail 20 -m integration tests/asset_meta/db/test_repository.py -v
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from tropek.db.models import Asset, AssetMetaClosure, AssetMetaSnapshot, AssetMetaValue, AssetType
from tropek.modules.asset_meta.repositories import AssetMetaRepository

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture()
async def test_asset(db_session: AsyncSession) -> Asset:
    """Create a minimal asset for FK satisfaction."""
    asset_type = AssetType(id=uuid.uuid4(), name=f'vm-{uuid.uuid4().hex[:8]}')
    db_session.add(asset_type)
    await db_session.flush()
    asset = Asset(
        id=uuid.uuid4(),
        name=f'test-asset-{uuid.uuid4().hex[:8]}',
        type_name=asset_type.name,
    )
    db_session.add(asset)
    await db_session.flush()
    return asset


async def test_insert_snapshot_returns_row_with_generated_id(
    db_session: AsyncSession,
    test_asset: Asset,
) -> None:
    """insert_snapshot should return a persisted row with all fields populated."""
    repository = AssetMetaRepository(db_session)
    observed = datetime(2026, 4, 16, 10, 0, 0, tzinfo=UTC)

    snapshot = await repository.insert_snapshot(
        asset_id=test_asset.id,
        source='prometheus',
        observed_at=observed,
    )

    assert snapshot.id is not None
    assert snapshot.asset_id == test_asset.id
    assert snapshot.source == 'prometheus'
    assert snapshot.observed_at == observed


async def test_insert_values_persists_all_entries(
    db_session: AsyncSession,
    test_asset: Asset,
) -> None:
    """insert_values should persist all provided key-value entries."""
    repository = AssetMetaRepository(db_session)
    observed = datetime(2026, 4, 16, 10, 0, 0, tzinfo=UTC)
    snapshot = await repository.insert_snapshot(
        asset_id=test_asset.id,
        source='prometheus',
        observed_at=observed,
    )

    entries = [
        (['hardware', 'cpu', 'model'], 'Intel Xeon'),
        (['hardware', 'cpu', 'cores'], '16'),
        (['hardware', 'memory', 'total_gb'], '64'),
    ]
    await repository.insert_values(snapshot.id, entries)
    await db_session.flush()

    persisted_values = await db_session.execute(select(AssetMetaValue).where(AssetMetaValue.snapshot_id == snapshot.id))
    rows = list(persisted_values.scalars().all())
    assert len(rows) == 3


async def test_insert_closures_persists_all_entries(
    db_session: AsyncSession,
    test_asset: Asset,
) -> None:
    """insert_closures should persist all provided closure paths."""
    repository = AssetMetaRepository(db_session)
    observed = datetime(2026, 4, 16, 10, 0, 0, tzinfo=UTC)
    snapshot = await repository.insert_snapshot(
        asset_id=test_asset.id,
        source='prometheus',
        observed_at=observed,
    )

    closure_paths = [
        ['hardware', 'cpu'],
        ['hardware', 'memory'],
    ]
    await repository.insert_closures(snapshot.id, closure_paths)
    await db_session.flush()

    persisted_closures = await db_session.execute(
        select(AssetMetaClosure).where(AssetMetaClosure.snapshot_id == snapshot.id)
    )
    rows = list(persisted_closures.scalars().all())
    assert len(rows) == 2


async def test_load_snapshots_for_derivation_respects_until_bound(
    db_session: AsyncSession,
    test_asset: Asset,
) -> None:
    """load_snapshots_for_derivation should only return snapshots with observed_at <= until."""
    repository = AssetMetaRepository(db_session)
    time_zero = datetime(2026, 4, 16, 10, 0, 0, tzinfo=UTC)
    time_one = time_zero + timedelta(hours=1)
    time_two = time_zero + timedelta(hours=2)

    await repository.insert_snapshot(asset_id=test_asset.id, source='src', observed_at=time_zero)
    await repository.insert_snapshot(asset_id=test_asset.id, source='src', observed_at=time_one)
    await repository.insert_snapshot(asset_id=test_asset.id, source='src', observed_at=time_two)

    loaded_snapshots = await repository.load_snapshots_for_derivation(
        asset_id=test_asset.id,
        until=time_one,
    )

    assert len(loaded_snapshots) == 2


async def test_load_snapshots_for_derivation_orders_by_observed_then_id(
    db_session: AsyncSession,
    test_asset: Asset,
) -> None:
    """Snapshots with identical observed_at should be ordered by id ASC."""
    repository = AssetMetaRepository(db_session)
    same_timestamp = datetime(2026, 4, 16, 10, 0, 0, tzinfo=UTC)

    snapshot_alpha = await repository.insert_snapshot(
        asset_id=test_asset.id,
        source='alpha',
        observed_at=same_timestamp,
    )
    snapshot_beta = await repository.insert_snapshot(
        asset_id=test_asset.id,
        source='beta',
        observed_at=same_timestamp,
    )

    expected_order = sorted(
        [snapshot_alpha, snapshot_beta],
        key=lambda snapshot: snapshot.id,
    )

    loaded_snapshots = await repository.load_snapshots_for_derivation(
        asset_id=test_asset.id,
        until=same_timestamp,
    )

    assert len(loaded_snapshots) == 2
    assert loaded_snapshots[0]['source'] == expected_order[0].source
    assert loaded_snapshots[1]['source'] == expected_order[1].source


async def test_load_snapshots_for_derivation_hydrates_values_and_closures(
    db_session: AsyncSession,
    test_asset: Asset,
) -> None:
    """Returned SnapshotRows should include associated values and closures."""
    repository = AssetMetaRepository(db_session)
    observed = datetime(2026, 4, 16, 10, 0, 0, tzinfo=UTC)
    snapshot = await repository.insert_snapshot(
        asset_id=test_asset.id,
        source='prometheus',
        observed_at=observed,
    )

    value_entries = [
        (['hardware', 'cpu', 'model'], 'Intel Xeon'),
        (['hardware', 'memory', 'total_gb'], '64'),
    ]
    await repository.insert_values(snapshot.id, value_entries)

    closure_paths = [['hardware', 'cpu']]
    await repository.insert_closures(snapshot.id, closure_paths)
    await db_session.flush()

    loaded_snapshots = await repository.load_snapshots_for_derivation(
        asset_id=test_asset.id,
        until=observed,
    )

    assert len(loaded_snapshots) == 1
    hydrated_snapshot = loaded_snapshots[0]
    assert len(hydrated_snapshot['values']) == 2
    assert len(hydrated_snapshot['closures']) == 1


async def test_cascade_delete_when_asset_removed(
    db_session: AsyncSession,
    test_asset: Asset,
) -> None:
    """Deleting an asset should cascade-delete all snapshots, values, and closures."""
    repository = AssetMetaRepository(db_session)
    observed = datetime(2026, 4, 16, 10, 0, 0, tzinfo=UTC)
    snapshot = await repository.insert_snapshot(
        asset_id=test_asset.id,
        source='prometheus',
        observed_at=observed,
    )

    await repository.insert_values(
        snapshot.id,
        [(['hardware', 'cpu', 'cores'], '16')],
    )
    await repository.insert_closures(
        snapshot.id,
        [['hardware', 'cpu']],
    )
    await db_session.flush()

    await db_session.execute(delete(Asset).where(Asset.id == test_asset.id))
    await db_session.flush()

    remaining_snapshots = await db_session.execute(
        select(AssetMetaSnapshot).where(AssetMetaSnapshot.asset_id == test_asset.id)
    )
    assert list(remaining_snapshots.scalars().all()) == []

    remaining_values = await db_session.execute(select(AssetMetaValue).where(AssetMetaValue.snapshot_id == snapshot.id))
    assert list(remaining_values.scalars().all()) == []

    remaining_closures = await db_session.execute(
        select(AssetMetaClosure).where(AssetMetaClosure.snapshot_id == snapshot.id)
    )
    assert list(remaining_closures.scalars().all()) == []
