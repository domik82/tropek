"""Tests for scenario profile generation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
from slo_generator.scenarios.degradation import DegradationScenario
from slo_generator.scenarios.healthy import HealthyScenario
from slo_generator.scenarios.outage import OutageScenario

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


class TestOutageScenario:
    def test_throughput_drops_during_outage(self):
        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=12)
        scenario = OutageScenario(start, end, outage_duration_minutes=30)

        chunks = list(scenario.generate(resolution_seconds=30))
        df = pd.concat(chunks)
        api = df[(df["service"] == "api") & (df["host"] == "host1")]

        # Pre-outage throughput should be healthy (~100 rps)
        pre = api[api["timestamp"] < start + timedelta(hours=6)]
        assert pre["throughput_rps"].mean() > 80

        # During outage throughput should be collapsed
        outage_start = start + timedelta(seconds=12 * 3600 * 0.60)
        outage_end = outage_start + timedelta(minutes=30)
        during = api[
            (api["timestamp"] >= outage_start + timedelta(minutes=5))
            & (api["timestamp"] < outage_end)
        ]
        if len(during) > 0:
            assert during["throughput_rps"].mean() < 20

    def test_error_rate_spikes_during_outage(self):
        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=12)
        scenario = OutageScenario(start, end, outage_duration_minutes=30)

        chunks = list(scenario.generate(resolution_seconds=30))
        df = pd.concat(chunks)
        api = df[(df["service"] == "api") & (df["host"] == "host1")]

        outage_start = start + timedelta(seconds=12 * 3600 * 0.60)
        outage_end = outage_start + timedelta(minutes=30)
        during = api[
            (api["timestamp"] >= outage_start + timedelta(minutes=5))
            & (api["timestamp"] < outage_end)
        ]
        if len(during) > 0:
            assert during["error_rate"].mean() > 0.5


class TestDegradationScenario:
    def test_throughput_unchanged_during_degradation(self):
        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=12)
        scenario = DegradationScenario(start, end)

        chunks = list(scenario.generate(resolution_seconds=30))
        df = pd.concat(chunks)
        api = df[(df["service"] == "api") & (df["host"] == "host1")]

        pre = api[api["timestamp"] < start + timedelta(hours=6)]
        post = api[api["timestamp"] > start + timedelta(hours=10)]

        # Throughput should be roughly the same pre and post deploy
        assert abs(pre["throughput_rps"].mean() - post["throughput_rps"].mean()) < 20

    def test_latency_increases_during_degradation(self):
        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=12)
        scenario = DegradationScenario(start, end)

        chunks = list(scenario.generate(resolution_seconds=30))
        df = pd.concat(chunks)
        api = df[(df["service"] == "api") & (df["host"] == "host1")]

        pre = api[api["timestamp"] < start + timedelta(hours=6)]
        post = api[api["timestamp"] > start + timedelta(hours=10)]

        # P99 should be roughly 5x higher after deployment
        assert post["p99_latency"].mean() > pre["p99_latency"].mean() * 3


class TestBaseScenarioGenerateWindow:
    def test_generate_window_returns_dataframe_with_correct_schema(self):
        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=24)
        scenario = HealthyScenario(start, end)

        # Request a 10-minute sub-window at 30s resolution
        window_start = start + timedelta(hours=5)
        window_end = window_start + timedelta(minutes=10)
        df = scenario.generate_window(window_start, window_end, resolution_seconds=30)

        validate_profile_schema(df)
        # 10 minutes at 30s = 20 timestamps x 6 service-host combos = 120 rows
        assert len(df) == 20 * 6

    def test_generate_window_timestamps_within_bounds(self):
        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=24)
        scenario = HealthyScenario(start, end)

        window_start = start + timedelta(hours=3)
        window_end = window_start + timedelta(minutes=5)
        df = scenario.generate_window(window_start, window_end, resolution_seconds=1)

        assert df["timestamp"].min() >= pd.Timestamp(window_start)
        assert df["timestamp"].max() < pd.Timestamp(window_end)

    def test_generate_window_empty_when_zero_duration(self):
        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=1)
        scenario = HealthyScenario(start, end)

        df = scenario.generate_window(start, start, resolution_seconds=1)
        assert len(df) == 0

    def test_event_mode_defaults_to_false(self):
        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=1)
        scenario = HealthyScenario(start, end)
        assert scenario.event_mode is False

    def test_event_mode_can_be_set(self):
        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=1)
        scenario = HealthyScenario(start, end, event_mode=True)
        assert scenario.event_mode is True
