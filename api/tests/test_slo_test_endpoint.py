# api/tests/test_slo_test_endpoint.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.db.session import get_session
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """TestClient with mocked DB session for unit tests."""
    mock_session = AsyncMock()
    # All repository lookups use result.scalar_one_or_none() — return None (not found) for all
    execute_result = MagicMock()
    execute_result.scalar_one_or_none = MagicMock(return_value=None)
    mock_session.execute = AsyncMock(return_value=execute_result)

    async def _mock_session():
        yield mock_session

    app.dependency_overrides[get_session] = _mock_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_slo_test_rejects_invalid_yaml(client):
    resp = client.post(
        "/slo-definitions/test",
        json={
            "slo_yaml": "{{invalid",
            "sli_name": "my-sli",
            "data_source_name": "prometheus",
            "asset_name": "vm-01",
            "period_start": "2026-03-01T00:00:00Z",
            "period_end": "2026-03-01T01:00:00Z",
        },
    )
    assert resp.status_code == 422
    assert "yaml" in resp.json()["detail"].lower() or "parse" in resp.json()["detail"].lower()


def test_slo_test_rejects_missing_required_fields(client):
    resp = client.post(
        "/slo-definitions/test",
        json={"slo_yaml": "spec_version: '1.0'"},
    )
    assert resp.status_code == 422


def test_slo_test_accepts_valid_request_shape(client):
    """Valid shape should not get 422 for request validation.

    It will likely get 404 for missing SLI/asset/datasource since there's no DB,
    but the request shape itself should be accepted.
    """
    resp = client.post(
        "/slo-definitions/test",
        json={
            "slo_yaml": (
                "spec_version: '1.0'\n"
                "indicators:\n"
                "  cpu: query\n"
                "objectives:\n"
                "  - sli: cpu\n"
                "    pass:\n"
                "      - criteria: ['<100']\n"
                "total_score:\n"
                "  pass: '90%'\n"
                "  warning: '75%'"
            ),
            "sli_name": "nonexistent-sli",
            "data_source_name": "nonexistent-ds",
            "asset_name": "nonexistent-asset",
            "period_start": "2026-03-01T00:00:00Z",
            "period_end": "2026-03-01T01:00:00Z",
        },
    )
    # Should be 404 (entity not found) not 422 (bad request shape)
    assert resp.status_code in (404, 502)
