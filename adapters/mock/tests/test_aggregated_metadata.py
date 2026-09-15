"""Tests for the mock adapter's aggregated-mode sample metadata."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from tropek_mock.main import QueryRequest, _handle_aggregated, _parse_interval


def _call_aggregated(*, start: datetime, end: datetime, interval: str) -> tuple[dict, dict, dict]:
    """Invoke the aggregated handler for an SLI the CSV store has no data for.

    :param datetime.datetime start: Evaluation window start.
    :param datetime.datetime end: Evaluation window end.
    :param str interval: Step spelling to exercise, e.g. ``1m``.
    :returns: The handler's ``(values, errors, metadata)`` dicts.
    :rtype: tuple[dict, dict, dict]
    """
    values: dict[str, Any] = {}
    errors: dict[str, str] = {}
    metadata: dict[str, Any] = {}
    _handle_aggregated(
        'no_such_metric',
        {'mode': 'aggregated', 'interval': interval, 'methods': ['mean']},
        QueryRequest(queries={'no_such_metric': 'no_such_metric'}, start=start, end=end),
        'default',
        values,
        errors,
        metadata,
    )
    return values, errors, metadata


def _run_aggregated(*, start: datetime, end: datetime, interval: str) -> dict[str, Any]:
    """Return just the metadata entry the handler produced for the SLI.

    :param datetime.datetime start: Evaluation window start.
    :param datetime.datetime end: Evaluation window end.
    :param str interval: Step spelling to exercise, e.g. ``1m``.
    :returns: The metadata entry for the SLI.
    :rtype: dict[str, typing.Any]
    """
    _values, _errors, metadata = _call_aggregated(start=start, end=end, interval=interval)
    return metadata['no_such_metric']


def test_expected_samples_counts_both_window_endpoints() -> None:
    """query_range evaluates at start and end, so a 5-step window expects 6 samples.

    The real Prometheus adapter counts it this way; the mock must agree or the UI shows
    different coverage against mock and live data.
    """
    entry = _run_aggregated(
        start=datetime(2026, 1, 15, 10, 0, tzinfo=UTC),
        end=datetime(2026, 1, 15, 10, 5, tzinfo=UTC),
        interval='1m',
    )
    assert entry['expected_samples'] == 6


def test_expected_samples_truncates_partial_trailing_step() -> None:
    """A window that is not a whole multiple of the step stops at the last whole step."""
    entry = _run_aggregated(
        start=datetime(2026, 1, 15, 10, 0, tzinfo=UTC),
        end=datetime(2026, 1, 15, 10, 5, tzinfo=UTC),
        interval='45s',
    )
    assert entry['expected_samples'] == 7


@pytest.mark.parametrize(('interval', 'seconds'), [('5s', 5), ('10s', 10), ('1m', 60), ('4h', 14400), ('1d', 86400)])
def test_parse_interval_accepts_a_whole_number_and_one_unit(interval: str, seconds: int) -> None:
    assert _parse_interval(interval) == seconds


@pytest.mark.parametrize('interval', ['90', '1m30s', '0s', '500ms', '1w', 'abc', '', 'm'])
def test_parse_interval_rejects_what_it_cannot_represent(interval: str) -> None:
    """Reject rather than guess: a bare '90' used to be read as 540 seconds, silently.

    The mock is what the UI is developed against, so a spelling the real adapter refuses must not
    quietly produce a different sample expectation here.
    """
    with pytest.raises(ValueError, match='interval'):
        _parse_interval(interval)


def test_unparseable_interval_fails_only_its_own_sli() -> None:
    """A bad step is reported against its SLI, not raised into a 500 that drops the whole request."""
    values, errors, metadata = _call_aggregated(
        start=datetime(2026, 1, 15, 10, 0, tzinfo=UTC),
        end=datetime(2026, 1, 15, 10, 5, tzinfo=UTC),
        interval='1m30s',
    )
    assert values['no_such_metric.mean'] is None
    assert '1m30s' in errors['no_such_metric.mean']
    assert 'no_such_metric' not in metadata
