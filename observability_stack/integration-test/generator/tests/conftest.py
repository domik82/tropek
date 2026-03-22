"""Shared test fixtures for the SLO generator."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest
from slo_generator.constants import PROFILE_COLUMNS
from slo_generator.raw import RawChunk, RawSample


@pytest.fixture
def sample_timestamps() -> list[datetime]:
    """One hour of timestamps at 1s resolution."""
    base = datetime(2026, 3, 20, 12, 0, 0, tzinfo=UTC)
    return [base + pd.Timedelta(seconds=i) for i in range(3600)]


@pytest.fixture
def sample_raw_chunk() -> RawChunk:
    """A small RawChunk (60 seconds, 1 service, 1 host) for unit tests."""
    base = datetime(2026, 3, 20, 12, 0, 0, tzinfo=UTC)
    rng = np.random.default_rng(42)
    samples: RawChunk = []
    for i in range(60):
        ts = base + pd.Timedelta(seconds=i)
        samples.append(
            RawSample(
                timestamp=ts,
                service="frontend",
                host="host1",
                request_count=100,
                error_count=1,
                latencies_ms=rng.lognormal(mean=3.0, sigma=0.4, size=100).tolist(),
                cpu_percent=40.0,
                memory_bytes=512 * 1024 * 1024,
            )
        )
    return samples


def raw_chunk_to_df(chunks: list[RawChunk]) -> pd.DataFrame:
    """Convert a list of RawChunks into a flat DataFrame for test assertions."""
    rows = [
        {
            "timestamp": s.timestamp,
            "service": s.service,
            "host": s.host,
            "request_count": s.request_count,
            "error_count": s.error_count,
            "latency_count": len(s.latencies_ms),
            "latency_median_ms": float(np.median(s.latencies_ms)) if s.latencies_ms else 0.0,
            "latency_p99_ms": float(np.percentile(s.latencies_ms, 99)) if s.latencies_ms else 0.0,
            "cpu_percent": s.cpu_percent,
            "memory_bytes": s.memory_bytes,
            "error_rate": s.error_count / s.request_count if s.request_count > 0 else 0.0,
        }
        for chunk in chunks
        for s in chunk
    ]
    return pd.DataFrame(rows)


def validate_profile_schema(df: pd.DataFrame) -> None:
    """Assert a DataFrame matches the legacy profile schema (for CSVScenario)."""
    assert list(df.columns) == PROFILE_COLUMNS
    assert df["timestamp"].dtype == "datetime64[ns, UTC]"
    assert df["service"].dtype.name == "category"
    assert df["host"].dtype.name == "category"


def validate_raw_chunk(chunk: RawChunk) -> None:
    """Assert a RawChunk has valid structure."""
    assert isinstance(chunk, list)
    assert all(isinstance(s, RawSample) for s in chunk)
    for s in chunk:
        assert s.request_count >= 0
        assert s.error_count >= 0
        assert s.error_count <= s.request_count
        assert len(s.latencies_ms) == s.request_count
        assert 0.0 <= s.cpu_percent <= 100.0
        assert s.memory_bytes >= 0
