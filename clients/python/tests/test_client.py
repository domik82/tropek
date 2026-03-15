from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock
from tropek_client.client import TropekClient
from tropek_client.exceptions import TropekNotFoundError

_UUID = "00000000-0000-0000-0000-000000000123"


def test_asset_types_list(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="http://test/asset-types",
        json={"items": [{"id": _UUID, "name": "vm", "is_default": True}]},
    )
    with TropekClient("http://test") as client:
        types = client.asset_types.list()
    assert len(types) == 1
    assert types[0].name == "vm"


def test_not_found_raises(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="http://test/assets/missing",
        status_code=404,
        json={"detail": "asset 'missing' not found"},
    )
    with TropekClient("http://test") as client, pytest.raises(TropekNotFoundError):
        client.assets.get("missing")


def test_slo_validate(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="http://test/slo-definitions/validate",
        json={"valid": False, "errors": [{"field": "spec_version", "message": "missing"}]},
    )
    with TropekClient("http://test") as client:
        result = client.slo_definitions.validate("bad yaml")
    assert result.valid is False
    assert len(result.errors) == 1
