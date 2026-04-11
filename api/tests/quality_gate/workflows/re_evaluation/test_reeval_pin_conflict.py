"""Unit tests for re-evaluation pin conflict schemas."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from tropek.modules.quality_gate.schemas.re_evaluation import ReEvaluateRequest
from tropek.modules.quality_gate.shared.exceptions import BaselinePinConflictError


class TestBaselinePinConflictError:
    def test_error_stores_pin_details(self) -> None:
        pin_date = datetime(2026, 3, 16, 10, 0, tzinfo=UTC)
        pin_id = uuid.uuid4()
        err = BaselinePinConflictError(pin_date, pin_id)

        assert err.pin_date == pin_date
        assert err.pin_evaluation_id == pin_id
        assert 'before the active baseline pin' in str(err)

    def test_error_is_exception(self) -> None:
        err = BaselinePinConflictError(datetime.now(tz=UTC), uuid.uuid4())
        assert isinstance(err, Exception)


class TestReEvaluateRequestPinStrategy:
    def test_pin_strategy_none_by_default(self) -> None:
        req = ReEvaluateRequest(
            asset_name='checkout-api',
            slo_name='http-slo',
            from_date=datetime(2026, 3, 15, tzinfo=UTC),
        )
        assert req.pin_strategy is None

    def test_pin_strategy_skip_to_pin(self) -> None:
        req = ReEvaluateRequest(
            asset_name='checkout-api',
            slo_name='http-slo',
            from_date=datetime(2026, 3, 15, tzinfo=UTC),
            pin_strategy='skip_to_pin',
        )
        assert req.pin_strategy == 'skip_to_pin'

    def test_pin_strategy_ignore_pin(self) -> None:
        req = ReEvaluateRequest(
            asset_name='checkout-api',
            slo_name='http-slo',
            from_date=datetime(2026, 3, 15, tzinfo=UTC),
            pin_strategy='ignore_pin',
        )
        assert req.pin_strategy == 'ignore_pin'

    def test_pin_strategy_invalid_value_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ReEvaluateRequest(
                asset_name='checkout-api',
                slo_name='http-slo',
                from_date=datetime(2026, 3, 15, tzinfo=UTC),
                pin_strategy='invalid',  # type: ignore[arg-type]
            )
