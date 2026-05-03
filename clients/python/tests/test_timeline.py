"""Tests for timeline endpoints."""

import httpx
import respx
from tropek_client.models import TimelineResponse

from .conftest import BASE_URL, load_fixture


class TestTimeline:
    @respx.mock
    def test_get(self, client):
        timeline_response = {'groups': [], 'items': []}
        respx.get(
            f'{BASE_URL}/assets/vm-01/meta/timeline',
            params={'from': '2026-03-01T00:00:00Z', 'to': '2026-03-01T01:00:00Z'},
        ).mock(return_value=httpx.Response(200, json=timeline_response))
        result = client.timeline.get('vm-01', from_='2026-03-01T00:00:00Z', to='2026-03-01T01:00:00Z')
        assert isinstance(result, TimelineResponse)
        assert result.groups == []
        assert result.items == []


class TestTimelineFixtures:
    @respx.mock
    def test_get(self, client):
        data = load_fixture('timeline_get')
        asset_id = 'fixture-asset-id'
        respx.get(
            f'{BASE_URL}/assets/{asset_id}/meta/timeline',
            params={'from': '2026-02-01T00:00:00Z', 'to': '2026-04-01T00:00:00Z'},
        ).mock(return_value=httpx.Response(200, json=data))
        result = client.timeline.get(
            asset_id,
            from_='2026-02-01T00:00:00Z',
            to='2026-04-01T00:00:00Z',
        )
        assert isinstance(result, TimelineResponse)
