# api/tests/test_slo_validate.py
from __future__ import annotations

import pytest
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    return TestClient(app)


def test_validate_valid_slo(client, slo_data):
    resp = client.post(
        "/slo-definitions/validate",
        json={"slo_yaml": slo_data("minimal.yaml")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is True
    assert body["errors"] == []
    assert body["objectives"] is not None
    assert len(body["objectives"]) > 0


def test_validate_invalid_yaml_syntax(client):
    resp = client.post(
        "/slo-definitions/validate",
        json={"slo_yaml": "{{invalid: yaml: ["},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is False
    assert len(body["errors"]) > 0
    assert body["objectives"] is None


def test_validate_missing_spec_version(client):
    resp = client.post(
        "/slo-definitions/validate",
        json={"slo_yaml": "objectives:\n  - sli: cpu\n"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is False
    assert any("spec_version" in e["message"] for e in body["errors"])


def test_validate_invalid_criteria_string(client):
    yaml_text = """spec_version: "1.0"
indicators:
  cpu: "query"
objectives:
  - sli: cpu
    pass:
      - criteria: [">>5"]
"""
    resp = client.post(
        "/slo-definitions/validate",
        json={"slo_yaml": yaml_text},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is False
    assert len(body["errors"]) > 0


def test_validate_empty_body(client):
    resp = client.post(
        "/slo-definitions/validate",
        json={"slo_yaml": ""},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is False
