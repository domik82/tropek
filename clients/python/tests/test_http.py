"""Tests for HTTP session layer."""

import httpx
import pytest
import respx
from tropek_client._http import HttpSession
from tropek_client.exceptions import (
    TropekConflictError,
    TropekConnectionError,
    TropekNotFoundError,
    TropekServerError,
    TropekValidationError,
)


@pytest.fixture
def session():
    return HttpSession(base_url='http://test-api:8080')


class TestHttpSession:
    @respx.mock
    def test_get_success(self, session):
        respx.get('http://test-api:8080/assets').mock(return_value=httpx.Response(200, json={'items': [], 'total': 0}))
        response = session.get('/assets')
        assert response.status_code == 200
        assert response.json() == {'items': [], 'total': 0}

    @respx.mock
    def test_post_sends_json_body(self, session):
        route = respx.post('http://test-api:8080/assets').mock(
            return_value=httpx.Response(201, json={'id': '123', 'name': 'test'})
        )
        session.post('/assets', json={'name': 'test', 'type_name': 'vm'})
        assert route.calls[0].request.content == b'{"name":"test","type_name":"vm"}'

    @respx.mock
    def test_404_raises_not_found(self, session):
        respx.get('http://test-api:8080/assets/missing').mock(
            return_value=httpx.Response(404, json={'detail': "asset 'missing' not found"})
        )
        with pytest.raises(TropekNotFoundError) as exc_info:
            session.get('/assets/missing')
        assert exc_info.value.entity == 'asset'
        assert exc_info.value.name == 'missing'

    @respx.mock
    def test_409_raises_conflict(self, session):
        respx.post('http://test-api:8080/assets').mock(
            return_value=httpx.Response(409, json={'detail': "asset 'dup': already exists"})
        )
        with pytest.raises(TropekConflictError):
            session.post('/assets', json={'name': 'dup'})

    @respx.mock
    def test_422_raises_validation(self, session):
        respx.post('http://test-api:8080/assets').mock(
            return_value=httpx.Response(
                422,
                json={'detail': [{'loc': ['body', 'name'], 'msg': 'field required', 'type': 'missing'}]},
            )
        )
        with pytest.raises(TropekValidationError) as exc_info:
            session.post('/assets', json={})
        assert len(exc_info.value.errors) == 1

    @respx.mock
    def test_500_raises_server_error(self, session):
        respx.get('http://test-api:8080/health').mock(
            return_value=httpx.Response(500, json={'detail': 'internal error'})
        )
        with pytest.raises(TropekServerError):
            session.get('/health')

    @respx.mock
    def test_connection_error(self, session):
        respx.get('http://test-api:8080/health').mock(side_effect=httpx.ConnectError('connection refused'))
        with pytest.raises(TropekConnectionError):
            session.get('/health')

    @respx.mock
    def test_timeout_error(self, session):
        respx.get('http://test-api:8080/health').mock(side_effect=httpx.TimeoutException('timed out'))
        with pytest.raises(TropekConnectionError):
            session.get('/health')

    def test_api_key_sets_header(self):
        session = HttpSession(base_url='http://test-api:8080', api_key='secret-key')
        assert session._client.headers.get('x-api-key') == 'secret-key'

    def test_custom_headers(self):
        session = HttpSession(base_url='http://test-api:8080', headers={'X-Custom': 'value'})
        assert session._client.headers.get('x-custom') == 'value'

    def test_context_manager(self):
        with HttpSession(base_url='http://test-api:8080') as session:
            assert session._client is not None
