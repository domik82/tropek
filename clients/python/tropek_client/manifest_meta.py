"""Meta snapshot manifest helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from tropek_client.models import MetaClosureInput, MetaSnapshotCreate, MetaValueInput

if TYPE_CHECKING:
    from tropek_client.manifest import ManifestDocument


def _normalize_timestamp(raw: str | datetime) -> str:
    """Normalize a timestamp to ISO 8601 UTC string for consistent comparison."""
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            raw = raw.replace(tzinfo=UTC)
        return raw.isoformat()
    return raw


def create_meta_snapshots(client: Any, doc: ManifestDocument) -> None:
    """Create meta snapshots for an asset, skipping any that already exist."""
    asset_name = doc.metadata['asset']
    asset = client.assets.get(asset_name)
    asset_id = str(asset.id)
    for snapshot_entry in doc.spec.get('snapshots', []):
        source = snapshot_entry['source']
        observed_at = _normalize_timestamp(snapshot_entry['observed_at'])
        existing = client.meta.list_snapshots(asset_id, source=source, from_=observed_at, to=observed_at)
        if existing:
            continue
        values = [
            MetaValueInput(label_path=v['label_path'], value=v['value']) for v in snapshot_entry.get('values', [])
        ]
        closed = [MetaClosureInput(label_path=c['label_path']) for c in snapshot_entry.get('closed', [])]
        body = MetaSnapshotCreate(
            source=source,
            observed_at=observed_at,
            values=values if values else None,
            closed=closed if closed else None,
        )
        client.meta.create_snapshot(asset_id, body)
