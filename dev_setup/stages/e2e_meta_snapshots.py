"""Meta snapshot CRUD integration tests."""

from __future__ import annotations

from tropek_client import TropekClient
from tropek_client.models import MetaSnapshotCreate, MetaValueInput


def step(name: str) -> None:
    """Print a step header."""
    print(f'\n=== {name} ===')


def test_meta_snapshot_crud(client: TropekClient) -> None:
    """Verify meta snapshots created by bootstrap manifests, then exercise get + delete."""
    step('Step 23: Meta snapshot CRUD')

    asset = client.assets.get('checkout-api')
    asset_id = str(asset.id)

    snapshots = client.meta.list_snapshots(asset_id)
    assert len(snapshots) >= 2, f'expected >= 2 bootstrap snapshots, got {len(snapshots)}'  # noqa: PLR2004
    print(f'listed {len(snapshots)} snapshots for checkout-api')

    cicd_snapshots = client.meta.list_snapshots(asset_id, source='cicd')
    assert all(s.source == 'cicd' for s in cicd_snapshots), 'filter returned non-cicd snapshot'
    print(f'filtered by source=cicd: {len(cicd_snapshots)} snapshots')

    snapshot_id = str(snapshots[0].id)
    detail = client.meta.get_snapshot(asset_id, snapshot_id)
    assert detail.source == snapshots[0].source
    assert len(detail.values) == snapshots[0].value_count
    print(f'detail: {len(detail.values)} values, {len(detail.closures)} closures')

    created = client.meta.create_snapshot(
        asset_id,
        MetaSnapshotCreate(
            source='e2e-test',
            observed_at='2026-03-20T00:00:00Z',
            values=[MetaValueInput(label_path=['e2e'], value='test')],
        ),
    )
    new_id = str(created.snapshot_id)
    print(f'created snapshot: {new_id}')

    client.meta.delete_snapshot(asset_id, new_id)
    after_delete = client.meta.list_snapshots(asset_id, source='e2e-test')
    assert len(after_delete) == 0, f'expected 0 after delete, got {len(after_delete)}'
    print('deleted snapshot verified')

    print('PASS: meta snapshot CRUD')
