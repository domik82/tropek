"""Tests for API response compression.

The grouped heatmap is ~10 MB of repetitive JSON (~0.6 MB gzipped). Clients that
talk to the API directly on :8080 (the Python client, CI pipelines) bypass the ui
nginx, so the API must compress on its own.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from tropek.main import app

# No `with`: the lifespan opens Redis/arq connections, and neither endpoint below needs them.
client = TestClient(app)


def test_large_response_is_gzipped_when_client_accepts_it():
    response = client.get('/openapi.json', headers={'Accept-Encoding': 'gzip'})

    assert response.status_code == 200
    assert response.headers['content-encoding'] == 'gzip'
    assert 'Accept-Encoding' in response.headers['vary']
    # httpx decodes transparently, so the body is still valid JSON.
    assert response.json()['info']['title'] == 'TROPEK API'


def test_response_is_not_compressed_when_client_does_not_accept_gzip():
    response = client.get('/openapi.json', headers={'Accept-Encoding': 'identity'})

    assert response.status_code == 200
    assert 'content-encoding' not in response.headers


def test_small_response_is_not_compressed():
    response = client.get('/health', headers={'Accept-Encoding': 'gzip'})

    assert response.status_code == 200
    assert 'content-encoding' not in response.headers
