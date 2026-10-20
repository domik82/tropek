import pytest
from tropek_prometheus.core.retry import compute_backoff


@pytest.mark.parametrize(('attempt', 'expected'), [(1, 1.0), (2, 2.0), (3, 4.0)])
def test_exponential_without_jitter(attempt: int, expected: float) -> None:
    assert compute_backoff(attempt, base_seconds=1.0, retry_after=None, jitter=0.0) == expected


def test_retry_after_seconds_wins() -> None:
    assert compute_backoff(1, base_seconds=1.0, retry_after='7', jitter=0.0) == 7.0


def test_retry_after_http_date_falls_back() -> None:
    # An HTTP-date is legal in Retry-After; we do not parse it, we fall back to the exponential value.
    assert compute_backoff(2, base_seconds=1.0, retry_after='Wed, 21 Oct 2026 07:28:00 GMT', jitter=0.0) == 2.0


def test_jitter_stays_within_band() -> None:
    values = {compute_backoff(1, base_seconds=4.0, retry_after=None, jitter=0.25) for _ in range(200)}
    assert all(3.0 <= value <= 5.0 for value in values)


@pytest.mark.parametrize(('retry_after', 'expected'), [('3600', 60.0), ('-5', 0.0)])
def test_retry_after_is_clamped_between_zero_and_sixty(retry_after: str, expected: float) -> None:
    assert compute_backoff(1, base_seconds=1.0, retry_after=retry_after, jitter=0.0) == expected


@pytest.mark.parametrize('retry_after', ['nan', 'inf', '-inf'])
def test_non_finite_retry_after_falls_back(retry_after: str) -> None:
    assert compute_backoff(2, base_seconds=1.0, retry_after=retry_after, jitter=0.0) == 2.0


def test_zero_base_never_sleeps_regardless_of_jitter() -> None:
    assert compute_backoff(3, base_seconds=0, retry_after=None, jitter=0.25) == 0
