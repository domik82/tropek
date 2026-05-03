"""Tests for configuration endpoints."""

import httpx
import respx
from tropek_client.models import ConfigurationRead

from .conftest import BASE_URL, load_fixture


class TestConfiguration:
    @respx.mock
    def test_list(self, client):
        config_json = {
            'name': 'max_comparison_results',
            'value': '5',
            'value_type': 'int',
            'description': 'Max results',
        }
        respx.get(f'{BASE_URL}/configuration').mock(return_value=httpx.Response(200, json=[config_json]))
        result = client.configuration.list()
        assert len(result) == 1
        assert isinstance(result[0], ConfigurationRead)
        assert result[0].name == 'max_comparison_results'

    @respx.mock
    def test_get(self, client):
        config_json = {
            'name': 'max_comparison_results',
            'value': '5',
            'value_type': 'int',
            'description': 'Max results',
        }
        respx.get(f'{BASE_URL}/configuration/max_comparison_results').mock(
            return_value=httpx.Response(200, json=config_json)
        )
        result = client.configuration.get('max_comparison_results')
        assert isinstance(result, ConfigurationRead)
        assert result.value == '5'

    @respx.mock
    def test_update(self, client):
        config_json = {
            'name': 'change_point.window_size',
            'value': '50',
            'value_type': 'int',
            'description': 'sliding window length',
        }
        route = respx.put(f'{BASE_URL}/configuration/change_point.window_size').mock(
            return_value=httpx.Response(200, json=config_json)
        )
        result = client.configuration.update('change_point.window_size', '50')
        assert isinstance(result, ConfigurationRead)
        assert result.value == '50'
        assert b'"value":"50"' in route.calls[0].request.content


class TestConfigurationFixtures:
    @respx.mock
    def test_list(self, client):
        data = load_fixture('configuration_list')
        respx.get(f'{BASE_URL}/configuration').mock(return_value=httpx.Response(200, json=data))
        result = client.configuration.list()
        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(item, ConfigurationRead) for item in result)

    @respx.mock
    def test_get(self, client):
        data = load_fixture('configuration_get')
        name = data['name']
        respx.get(f'{BASE_URL}/configuration/{name}').mock(
            return_value=httpx.Response(200, json=data),
        )
        result = client.configuration.get(name)
        assert isinstance(result, ConfigurationRead)
        assert result.name == name
