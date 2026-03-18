"""Unit tests for re-evaluation schemas and logic."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from app.modules.quality_gate.re_evaluation_schemas import ReEvaluateRequest
from pydantic import ValidationError


def test_request_requires_exactly_one_scope() -> None:
    with pytest.raises(ValidationError, match="exactly one"):
        ReEvaluateRequest(asset_name="x", slo_name="y")


def test_request_rejects_multiple_scopes() -> None:
    with pytest.raises(ValidationError, match="exactly one"):
        ReEvaluateRequest(
            asset_name="x",
            slo_name="y",
            from_date=datetime(2026, 3, 10, tzinfo=UTC),
            from_baseline=True,
        )


def test_request_accepts_from_date() -> None:
    req = ReEvaluateRequest(
        asset_name="x",
        slo_name="y",
        from_date=datetime(2026, 3, 10, tzinfo=UTC),
    )
    assert req.from_date is not None


def test_request_accepts_from_baseline() -> None:
    req = ReEvaluateRequest(asset_name="x", slo_name="y", from_baseline=True)
    assert req.from_baseline


def test_request_accepts_from_evaluation_id() -> None:
    eid = uuid.uuid4()
    req = ReEvaluateRequest(asset_name="x", slo_name="y", from_evaluation_id=eid)
    assert req.from_evaluation_id == eid
