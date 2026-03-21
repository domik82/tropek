"""Shared test fixtures for the SLO generator."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest
from slo_generator.constants import PROFILE_COLUMNS


@pytest.fixture
def sample_timestamps() -> list[datetime]:
    """One hour of timestamps at 1s resolution."""
    base = datetime(2026, 3, 20, 12, 0, 0, tzinfo=UTC)
    return [base + pd.Timedelta(seconds=i) for i in range(3600)]


@pytest.fixture
def sample_profile_chunk() -> pd.DataFrame:
    """A small profile DataFrame (60 seconds, 1 service, 1 host) for unit tests."""
    base = datetime(2026, 3, 20, 12, 0, 0, tzinfo=UTC)
    timestamps = [base + pd.Timedelta(seconds=i) for i in range(60)]
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(timestamps, utc=True),
            "service": pd.Categorical(["frontend"] * 60),
            "host": pd.Categorical(["host1"] * 60),
            "throughput_rps": [100.0] * 60,
            "error_rate": [0.001] * 60,
            "p50_latency": [0.020] * 60,
            "p99_latency": [0.080] * 60,
            "cpu_percent": [40.0] * 60,
            "memory_bytes": [512 * 1024 * 1024] * 60,
        }
    )


def validate_profile_schema(df: pd.DataFrame) -> None:
    """Assert a DataFrame matches the profile schema."""
    assert list(df.columns) == PROFILE_COLUMNS
    assert df["timestamp"].dtype == "datetime64[ns, UTC]"
    assert df["service"].dtype.name == "category"
    assert df["host"].dtype.name == "category"
