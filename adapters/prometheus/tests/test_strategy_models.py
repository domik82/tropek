"""Tests for the strategy result models."""

import pytest
from pydantic import ValidationError
from tropek_prometheus.core.strategies.models import ErrorKind, IndicatorOutcome


@pytest.mark.parametrize(
    ('error', 'error_kind'),
    [('x', None), (None, 'data')],
    ids=['error_without_kind', 'kind_without_error'],
)
def test_outcome_requires_error_kind_exactly_when_error_is_set(error: str | None, error_kind: ErrorKind | None) -> None:
    with pytest.raises(ValidationError, match='error_kind'):
        IndicatorOutcome(value=None, error=error, error_kind=error_kind)
