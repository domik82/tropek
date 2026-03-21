"""Tests for scenario profile generation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd

from tests.conftest import validate_profile_schema


class TestHealthyScenario:
    def test_generates_profile_dataframe_with_correct_schema(self):
        from slo_generator.scenarios.healthy import HealthyScenario

        start = datetime(2026, 3, 20, 12, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=1)
        scenario = HealthyScenario(start, end)

        chunks = list(scenario.generate(resolution_seconds=1))
        assert len(chunks) == 1  # 1 hour = 1 chunk
        df = chunks[0]
        validate_profile_schema(df)

    def test_produces_rows_for_all_service_host_combos(self):
        from slo_generator.scenarios.healthy import HealthyScenario

        start = datetime(2026, 3, 20, 12, 0, 0, tzinfo=UTC)
        end = start + timedelta(minutes=1)
        scenario = HealthyScenario(start, end)

        chunks = list(scenario.generate(resolution_seconds=1))
        df = pd.concat(chunks)

        services = set(df["service"].unique())
        hosts = set(df["host"].unique())
        assert services == {"frontend", "api", "backend"}
        assert hosts == {"host1", "host2"}

    def test_throughput_has_diurnal_variation(self):
        from slo_generator.scenarios.healthy import HealthyScenario

        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=24)
        scenario = HealthyScenario(start, end)

        chunks = list(scenario.generate(resolution_seconds=60))
        df = pd.concat(chunks)

        # Filter to one service-host combo
        mask = (df["service"] == "api") & (df["host"] == "host1")
        series = df.loc[mask, "throughput_rps"]

        # Should vary by ~±15%, not flat
        assert series.std() > 1.0  # not a flat line
        assert series.min() > 50.0  # reasonable lower bound
        assert series.max() < 200.0  # reasonable upper bound

    def test_values_within_healthy_bounds(self):
        from slo_generator.scenarios.healthy import HealthyScenario

        start = datetime(2026, 3, 20, 12, 0, 0, tzinfo=UTC)
        end = start + timedelta(minutes=10)
        scenario = HealthyScenario(start, end)

        chunks = list(scenario.generate(resolution_seconds=1))
        df = pd.concat(chunks)

        assert (df["error_rate"] >= 0).all()
        assert (df["error_rate"] < 0.01).all()
        assert (df["cpu_percent"] >= 0).all()
        assert (df["cpu_percent"] <= 100).all()
        assert (df["p99_latency"] > 0).all()
        assert (df["p99_latency"] < 1.0).all()

    def test_chunked_output_bounds_memory(self):
        from slo_generator.scenarios.healthy import HealthyScenario

        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=3)
        scenario = HealthyScenario(start, end)

        chunks = list(scenario.generate(resolution_seconds=1))
        # 3 hours should produce 3 chunks (1 per hour)
        assert len(chunks) == 3

        # Each chunk should have roughly 1 hour of data
        for chunk in chunks:
            duration = chunk["timestamp"].max() - chunk["timestamp"].min()
            assert duration <= pd.Timedelta(hours=1)
