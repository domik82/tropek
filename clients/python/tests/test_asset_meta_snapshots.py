"""Tests for meta snapshot endpoints."""

import httpx
import respx
from tropek_client.models import MetaSnapshotCreate, MetaSnapshotCreated

from .conftest import BASE_URL, UUID1


class TestMeta:
    @respx.mock
    def test_create_snapshot(self, client):
        route = respx.post(f'{BASE_URL}/assets/vm-01/meta/snapshots').mock(
            return_value=httpx.Response(201, json={'snapshot_id': UUID1})
        )
        result = client.meta.create_snapshot(
            'vm-01',
            MetaSnapshotCreate(source='ci', observed_at='2026-01-01T00:00:00Z'),
        )
        assert isinstance(result, MetaSnapshotCreated)
        assert route.called
