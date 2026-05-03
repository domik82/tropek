"""Tests for health endpoint."""

import httpx
import respx

from .conftest import BASE_URL


class TestHealth:
    @respx.mock
    def test_health(self, client):
        respx.get(f'{BASE_URL}/health').mock(return_value=httpx.Response(200, json={'status': 'ok'}))
        result = client.health()
        assert result == {'status': 'ok'}
