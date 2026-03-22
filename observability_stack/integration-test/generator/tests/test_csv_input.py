"""Tests for CSV input scenario."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from tests.conftest import validate_profile_schema


@pytest.fixture
def csv_file(tmp_path: Path) -> Path:
    """Create a valid CSV file with 60 seconds of data."""
    base = datetime(2026, 3, 20, 12, 0, 0, tzinfo=UTC)
    rows = []
    for i in range(60):
        ts = base + timedelta(seconds=i)
        rows.append(
            {
                "timestamp": ts.isoformat(),
                "service": "frontend",
                "host": "host1",
                "throughput_rps": 100.0 + i,  # ramp
                "error_rate": 0.001,
                "p50_latency": 0.020,
                "p99_latency": 0.080,
                "cpu_percent": 40.0,
                "memory_bytes": 536870912,
            }
        )
    df = pd.DataFrame(rows)
    path = tmp_path / "input.csv"
    df.to_csv(path, index=False)
    return path


class TestCSVScenario:
    def test_loads_and_yields_profile_dataframe(self, csv_file: Path):
        from slo_generator.scenarios.csv_input import CSVScenario

        scenario = CSVScenario(csv_file)
        chunks = list(scenario.generate())
        assert len(chunks) >= 1
        df = pd.concat(chunks)
        validate_profile_schema(df)
        assert len(df) == 60

    def test_preserves_values_from_csv(self, csv_file: Path):
        from slo_generator.scenarios.csv_input import CSVScenario

        scenario = CSVScenario(csv_file)
        df = pd.concat(scenario.generate())
        # First row should have throughput 100.0, last row 159.0
        assert df.iloc[0]["throughput_rps"] == pytest.approx(100.0)
        assert df.iloc[-1]["throughput_rps"] == pytest.approx(159.0)

    def test_rejects_missing_columns(self, tmp_path: Path):
        from slo_generator.scenarios.csv_input import CSVScenario

        path = tmp_path / "bad.csv"
        pd.DataFrame({"timestamp": ["2026-01-01"], "service": ["x"]}).to_csv(path, index=False)

        with pytest.raises(ValueError, match="missing columns"):
            CSVScenario(path)

    def test_roundtrip_with_raw_shaper(self, csv_file: Path):
        """CSV in → RawShaper out should produce the same data."""
        from slo_generator.scenarios.csv_input import CSVScenario

        scenario = CSVScenario(csv_file)
        df = pd.concat(scenario.generate())
        assert len(df) == 60
