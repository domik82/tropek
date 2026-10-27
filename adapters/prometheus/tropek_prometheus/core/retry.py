"""Backoff computation shared by the Prometheus client (and any future outbound call)."""

from __future__ import annotations

import math
import random

MAX_BACKOFF_SECONDS = 60.0

# Jitter needs no seeding or reproducibility; SystemRandom also avoids the shared global state of the ``random`` module.
_jitter_random = random.SystemRandom()


def compute_backoff(attempt: int, *, base_seconds: float, retry_after: str | None, jitter: float = 0.25) -> float:
    """Return the seconds to wait after a failed attempt, never less than 0 nor more than 60.

    ``Retry-After`` in seconds wins when present, numeric and finite; an HTTP-date or non-finite value is
    ignored (dates are not parsed, the exponential value is a safe fallback). Otherwise the delay is
    ``base_seconds * 2 ** (attempt - 1)`` with ``+/- jitter`` relative noise.

    Args:
        attempt: The 1-based number of the attempt that just failed.
        base_seconds: Delay after the first failed attempt; doubles for each further one.
        retry_after: Raw ``Retry-After`` header value, or ``None`` when the response had none.
        jitter: Relative noise applied to the exponential delay (``0`` disables it).

    Returns:
        Seconds to sleep before the next attempt, between 0 and ``MAX_BACKOFF_SECONDS``.
    """
    delay: float | None = None
    if retry_after is not None:
        try:
            retry_after_seconds = float(retry_after)
        except ValueError:
            retry_after_seconds = math.nan
        if math.isfinite(retry_after_seconds):
            delay = retry_after_seconds
    if delay is None:
        delay = base_seconds * (2.0 ** (attempt - 1))
        if jitter:
            delay *= 1 + _jitter_random.uniform(-jitter, jitter)
    return min(max(delay, 0.0), MAX_BACKOFF_SECONDS)
