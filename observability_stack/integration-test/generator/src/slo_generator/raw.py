"""Raw data model — single source of truth for all backends."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

# Type alias for a chunk of raw samples (one chunk = one hour of data typically)
RawChunk = list["RawSample"]


@dataclass
class RawSample:
    """One second of raw data for a single (service, host) combination.

    This is the atomic unit of generated data. All backend-specific
    representations (Prometheus histogram buckets, InfluxDB points,
    TimescaleDB rows) are derived from these samples.
    """

    timestamp: datetime
    service: str
    host: str
    request_count: int
    error_count: int
    latencies_ms: list[float] = field(default_factory=list)
    cpu_percent: float = 0.0
    memory_bytes: float = 0.0


def generate_latencies(
    count: int,
    base_ms: float,
    sigma: float,
    rng: np.random.Generator,
) -> list[float]:
    """Generate individual request latencies from a lognormal distribution.

    Args:
        count: Number of latency samples to generate (= successful request count).
        base_ms: Median latency in milliseconds (becomes the lognormal mu).
        sigma: Distribution width (lognormal sigma, default ~0.4).
        rng: NumPy random generator for reproducibility.

    Returns:
        List of latency values in milliseconds, length == count.
    """
    if count <= 0:
        return []
    base_ms = max(base_ms, 0.01)
    mu = math.log(base_ms)
    samples = rng.lognormal(mean=mu, sigma=sigma, size=count)
    return samples.tolist()


def apply_jitter(value: float, jitter_pct: float, rng: np.random.Generator) -> float:
    """Apply random jitter to a value.

    Args:
        value: Base value to jitter.
        jitter_pct: Jitter range as a fraction (0.05 = ±5%). 0 = no jitter.
        rng: NumPy random generator.

    Returns:
        Jittered value. If jitter_pct is 0, returns value unchanged.
    """
    if jitter_pct <= 0:
        return value
    factor = 1.0 + rng.uniform(-jitter_pct, jitter_pct)
    return value * factor


def generate_errors(
    request_count: int,
    error_rate: float,
    rng: np.random.Generator,
) -> int:
    """Generate error count from a binomial distribution.

    Args:
        request_count: Total requests this second.
        error_rate: Probability of each request being an error (0.01 = 1%).
        rng: NumPy random generator.

    Returns:
        Number of failed requests (0 to request_count).
    """
    if request_count <= 0 or error_rate <= 0:
        return 0
    if error_rate >= 1.0:
        return request_count
    return int(rng.binomial(request_count, error_rate))
