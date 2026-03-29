# api/tests/test_slo_validate.py
from __future__ import annotations

import pytest
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    return TestClient(app)


VALID_OBJECTIVES = [{'sli': 'response_time_p99', 'pass_criteria': ['<600'], 'weight': 1}]
INVALID_CRITERIA_OBJECTIVES = [{'sli': 'cpu', 'pass_criteria': ['>>5']}]


def test_validate_valid_slo(client):
    resp = client.post(
        '/slo-definitions/validate',
        json={'objectives': VALID_OBJECTIVES},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body['valid'] is True
    assert body['errors'] == []
    assert body['objectives'] is not None
    assert len(body['objectives']) > 0


def test_validate_empty_objectives(client):
    resp = client.post(
        '/slo-definitions/validate',
        json={'objectives': []},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body['valid'] is False
    assert len(body['errors']) > 0
    assert body['objectives'] is None


def test_validate_invalid_criteria_string(client):
    resp = client.post(
        '/slo-definitions/validate',
        json={'objectives': INVALID_CRITERIA_OBJECTIVES},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body['valid'] is False
    assert len(body['errors']) > 0


def test_validate_missing_objectives_field(client):
    resp = client.post(
        '/slo-definitions/validate',
        json={'total_score_pass_pct': 90.0},
    )
    assert resp.status_code == 422


def test_validate_custom_score_thresholds(client):
    resp = client.post(
        '/slo-definitions/validate',
        json={
            'objectives': VALID_OBJECTIVES,
            'total_score_pass_pct': 80.0,
            'total_score_warning_pct': 60.0,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body['valid'] is True
