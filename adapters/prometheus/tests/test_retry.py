import pytest
from tropek_prometheus.core.retry import compute_backoff


@pytest.mark.parametrize(('attempt', 'expected'), [(1, 1.0), (2, 2.0), (3, 4.0)])
def test_exponential_without_jitter(attempt: int, expected: float) -> None:
    assert compute_backoff(attempt, base_seconds=1.0, retry_after=None, jitter=0.0) == expected


@pytest.mark.parametrize(
    ('retry_after', 'expected'),
    [
        ('7', 7.0),
        ('3600', 60.0),
        ('-5', 0.0),
        # An HTTP-date is legal in Retry-After; we do not parse it, we fall back to the exponential value.
        ('Wed, 21 Oct 2026 07:28:00 GMT', 2.0),
        ('nan', 2.0),
        ('inf', 2.0),
        ('-inf', 2.0),
    ],
)
def test_retry_after_header_handling(retry_after: str, expected: float) -> None:
    assert compute_backoff(2, base_seconds=1.0, retry_after=retry_after, jitter=0.0) == expected


def test_jitter_varies_the_delay_within_band() -> None:
    values = [compute_backoff(1, base_seconds=4.0, retry_after=None, jitter=0.25) for _ in range(200)]
    assert all(3.0 <= value <= 5.0 for value in values)
    assert len(set(values)) > 1
