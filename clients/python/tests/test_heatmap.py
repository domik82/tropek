"""Tests for heatmap endpoints."""

import httpx
import respx
from tropek_client.models import GroupedMetricHeatmapResponse

from .conftest import BASE_URL, load_fixture


class TestHeatmap:
    @respx.mock
    def test_grouped(self, client):
        heatmap_response = {
            'asset_name': 'vm-01',
            'columns': [],
            'groups': [],
            'composite': [],
        }
        respx.get(f'{BASE_URL}/evaluations/heatmap', params={'asset_name': 'vm-01'}).mock(
            return_value=httpx.Response(200, json=heatmap_response)
        )
        result = client.heatmap.grouped('vm-01')
        assert isinstance(result, GroupedMetricHeatmapResponse)
        assert result.asset_name == 'vm-01'
        assert result.groups == []


class TestHeatmapFixtures:
    @respx.mock
    def test_grouped(self, client):
        data = load_fixture('heatmap_grouped')
        respx.get(f'{BASE_URL}/evaluations/heatmap', params={'asset_name': 'checkout-api'}).mock(
            return_value=httpx.Response(200, json=data)
        )
        result = client.heatmap.grouped('checkout-api')
        assert isinstance(result, GroupedMetricHeatmapResponse)
        assert result.asset_name == 'checkout-api'
