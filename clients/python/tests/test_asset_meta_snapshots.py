"""Tests for meta snapshot endpoints."""

import httpx
import respx
from tropek_client.models import (
    MetaClosureOutput,
    MetaSnapshotCreate,
    MetaSnapshotCreated,
    MetaSnapshotDetail,
    MetaSnapshotSummary,
    MetaValueInput,
    MetaValueOutput,
)

from .conftest import BASE_URL, UUID1, UUID2


class TestMeta:
    @respx.mock
    def test_create_snapshot(self, client):
        route = respx.post(f'{BASE_URL}/assets/vm-01/meta/snapshots').mock(
            return_value=httpx.Response(201, json={'snapshot_id': UUID1})
        )
        result = client.meta.create_snapshot(
            'vm-01',
            MetaSnapshotCreate(
                source='ci',
                observed_at='2026-01-01T00:00:00Z',
                values=[MetaValueInput(label_path=['app'], value='1.0')],
            ),
        )
        assert isinstance(result, MetaSnapshotCreated)
        assert route.called

    @respx.mock
    def test_list_snapshots(self, client):
        route = respx.get(f'{BASE_URL}/assets/vm-01/meta/snapshots').mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        'id': UUID1,
                        'source': 'cicd',
                        'observed_at': '2026-04-16T10:00:00Z',
                        'value_count': 2,
                        'closure_count': 0,
                        'created_at': '2026-04-16T10:00:01Z',
                    }
                ],
            )
        )
        result = client.meta.list_snapshots('vm-01')
        assert len(result) == 1
        assert isinstance(result[0], MetaSnapshotSummary)
        assert result[0].source == 'cicd'
        assert result[0].value_count == 2
        assert route.called

    @respx.mock
    def test_list_snapshots_with_filters(self, client):
        route = respx.get(
            f'{BASE_URL}/assets/vm-01/meta/snapshots',
            params={
                'source': 'cicd',
                'from': '2026-04-16T00:00:00Z',
                'to': '2026-04-17T00:00:00Z',
            },
        ).mock(return_value=httpx.Response(200, json=[]))
        result = client.meta.list_snapshots(
            'vm-01',
            source='cicd',
            from_='2026-04-16T00:00:00Z',
            to='2026-04-17T00:00:00Z',
        )
        assert result == []
        assert route.called

    @respx.mock
    def test_get_snapshot(self, client):
        route = respx.get(f'{BASE_URL}/assets/vm-01/meta/snapshots/{UUID1}').mock(
            return_value=httpx.Response(
                200,
                json={
                    'id': UUID1,
                    'source': 'cicd',
                    'observed_at': '2026-04-16T10:00:00Z',
                    'created_at': '2026-04-16T10:00:01Z',
                    'values': [{'label_path': ['app'], 'value': '1.0'}],
                    'closures': [{'label_path': ['old']}],
                },
            )
        )
        result = client.meta.get_snapshot('vm-01', UUID1)
        assert isinstance(result, MetaSnapshotDetail)
        assert result.source == 'cicd'
        assert len(result.values) == 1
        assert isinstance(result.values[0], MetaValueOutput)
        assert result.values[0].label_path == ['app']
        assert len(result.closures) == 1
        assert isinstance(result.closures[0], MetaClosureOutput)
        assert result.closures[0].label_path == ['old']
        assert route.called

    @respx.mock
    def test_delete_snapshot(self, client):
        route = respx.delete(f'{BASE_URL}/assets/vm-01/meta/snapshots/{UUID2}').mock(return_value=httpx.Response(204))
        client.meta.delete_snapshot('vm-01', UUID2)
        assert route.called
