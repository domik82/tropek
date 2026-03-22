"""Tests for scenario raw sample generation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from slo_generator.scenarios.degradation import DegradationScenario
from slo_generator.scenarios.healthy import HealthyScenario
from slo_generator.scenarios.memory_leak import MemoryLeakScenario
from slo_generator.scenarios.outage import OutageScenario
from slo_generator.scenarios.polska import PolskaScenario
from slo_generator.scenarios.step_change import StepChangeScenario
from slo_generator.scenarios.traffic_spike import TrafficSpikeScenario

from tests.conftest import raw_chunk_to_df, validate_raw_chunk


class TestHealthyScenario:
    def test_generates_raw_chunk_with_correct_structure(self):
        start = datetime(2026, 3, 20, 12, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=1)
        scenario = HealthyScenario(start, end)

        chunks = list(scenario.generate(resolution_seconds=1))
        assert len(chunks) == 1
        validate_raw_chunk(chunks[0])

    def test_produces_samples_for_all_service_host_combos(self):
        start = datetime(2026, 3, 20, 12, 0, 0, tzinfo=UTC)
        end = start + timedelta(minutes=1)
        scenario = HealthyScenario(start, end)

        chunks = list(scenario.generate(resolution_seconds=1))
        df = raw_chunk_to_df(chunks)

        services = set(df["service"].unique())
        hosts = set(df["host"].unique())
        assert services == {"frontend", "api", "backend"}
        assert hosts == {"host1", "host2"}

    def test_throughput_has_diurnal_variation(self):
        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=24)
        scenario = HealthyScenario(start, end)

        chunks = list(scenario.generate(resolution_seconds=60))
        df = raw_chunk_to_df(chunks)

        mask = (df["service"] == "api") & (df["host"] == "host1")
        series = df.loc[mask, "request_count"]

        assert series.std() > 1.0
        assert series.min() > 10
        assert series.max() < 200

    def test_values_within_healthy_bounds(self):
        start = datetime(2026, 3, 20, 12, 0, 0, tzinfo=UTC)
        end = start + timedelta(minutes=10)
        scenario = HealthyScenario(start, end)

        chunks = list(scenario.generate(resolution_seconds=1))
        df = raw_chunk_to_df(chunks)

        assert (df["error_rate"] >= 0).all()
        assert (df["error_rate"] < 0.15).all()  # binomial noise on ~100 requests
        assert (df["cpu_percent"] >= 0).all()
        assert (df["cpu_percent"] <= 100).all()
        assert (df["latency_p99_ms"] > 0).all()

    def test_chunked_output_bounds_memory(self):
        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=3)
        scenario = HealthyScenario(start, end)

        chunks = list(scenario.generate(resolution_seconds=1))
        assert len(chunks) == 3

        for chunk in chunks:
            timestamps = [s.timestamp for s in chunk]
            duration = max(timestamps) - min(timestamps)
            assert duration <= timedelta(hours=1)


class TestOutageScenario:
    def test_throughput_drops_during_outage(self):
        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=12)
        scenario = OutageScenario(start, end, outage_duration_minutes=30)

        chunks = list(scenario.generate(resolution_seconds=30))
        df = raw_chunk_to_df(chunks)
        api = df[(df["service"] == "api") & (df["host"] == "host1")]

        pre = api[api["timestamp"] < start + timedelta(hours=6)]
        assert pre["request_count"].mean() > 80

        outage_start = start + timedelta(seconds=12 * 3600 * 0.60)
        outage_end = outage_start + timedelta(minutes=30)
        during = api[
            (api["timestamp"] >= outage_start + timedelta(minutes=5))
            & (api["timestamp"] < outage_end)
        ]
        if len(during) > 0:
            assert during["request_count"].mean() < 20

    def test_error_rate_spikes_during_outage(self):
        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=12)
        scenario = OutageScenario(start, end, outage_duration_minutes=30)

        chunks = list(scenario.generate(resolution_seconds=30))
        df = raw_chunk_to_df(chunks)
        api = df[(df["service"] == "api") & (df["host"] == "host1")]

        outage_start = start + timedelta(seconds=12 * 3600 * 0.60)
        outage_end = outage_start + timedelta(minutes=30)
        during = api[
            (api["timestamp"] >= outage_start + timedelta(minutes=5))
            & (api["timestamp"] < outage_end)
        ]
        if len(during) > 0:
            assert during["error_rate"].mean() > 0.3


class TestDegradationScenario:
    def test_throughput_unchanged_during_degradation(self):
        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=12)
        scenario = DegradationScenario(start, end)

        chunks = list(scenario.generate(resolution_seconds=30))
        df = raw_chunk_to_df(chunks)
        api = df[(df["service"] == "api") & (df["host"] == "host1")]

        pre = api[api["timestamp"] < start + timedelta(hours=6)]
        post = api[api["timestamp"] > start + timedelta(hours=10)]

        assert abs(pre["request_count"].mean() - post["request_count"].mean()) < 20

    def test_latency_increases_during_degradation(self):
        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=12)
        scenario = DegradationScenario(start, end)

        chunks = list(scenario.generate(resolution_seconds=30))
        df = raw_chunk_to_df(chunks)
        api = df[(df["service"] == "api") & (df["host"] == "host1")]

        pre = api[api["timestamp"] < start + timedelta(hours=6)]
        post = api[api["timestamp"] > start + timedelta(hours=10)]

        assert post["latency_p99_ms"].mean() > pre["latency_p99_ms"].mean() * 3


class TestBaseScenarioGenerateWindow:
    def test_generate_window_returns_raw_chunk(self):
        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=24)
        scenario = HealthyScenario(start, end)

        window_start = start + timedelta(hours=5)
        window_end = window_start + timedelta(minutes=10)
        chunk = scenario.generate_window(window_start, window_end, resolution_seconds=30)

        validate_raw_chunk(chunk)
        # 10 minutes at 30s = 20 timestamps x 6 service-host combos = 120 samples
        assert len(chunk) == 20 * 6

    def test_generate_window_timestamps_within_bounds(self):
        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=24)
        scenario = HealthyScenario(start, end)

        window_start = start + timedelta(hours=3)
        window_end = window_start + timedelta(minutes=5)
        chunk = scenario.generate_window(window_start, window_end, resolution_seconds=1)

        timestamps = [s.timestamp for s in chunk]
        assert min(timestamps) >= window_start
        assert max(timestamps) < window_end

    def test_generate_window_empty_when_zero_duration(self):
        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=1)
        scenario = HealthyScenario(start, end)

        chunk = scenario.generate_window(start, start, resolution_seconds=1)
        assert len(chunk) == 0

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


class TestOutageEventMode:
    def test_event_mode_outage_fills_entire_window(self):
        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(minutes=45)
        scenario = OutageScenario(start, end, event_mode=True, recovery_minutes=10)

        chunks = list(scenario.generate(resolution_seconds=30))
        df = raw_chunk_to_df(chunks)
        api = df[(df["service"] == "api") & (df["host"] == "host1")]

        early = api[api["timestamp"] < start + timedelta(minutes=10)]
        assert early["error_rate"].mean() > 0.3

    def test_event_mode_recovery_ends_at_window_end(self):
        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(minutes=40)
        scenario = OutageScenario(start, end, event_mode=True, recovery_minutes=10)

        assert scenario.recovery_end == end

    def test_standalone_mode_unchanged(self):
        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=12)
        scenario = OutageScenario(start, end)

        expected_start = start + timedelta(seconds=12 * 3600 * 0.60)
        assert abs((scenario.outage_start - expected_start).total_seconds()) < 1


class TestDegradationEventMode:
    def test_event_mode_ramp_starts_at_window_start(self):
        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=2)
        scenario = DegradationScenario(start, end, event_mode=True, ramp_minutes=5)

        chunks = list(scenario.generate(resolution_seconds=30))
        df = raw_chunk_to_df(chunks)
        api = df[(df["service"] == "api") & (df["host"] == "host1")]

        post_ramp = api[api["timestamp"] >= start + timedelta(minutes=10)]
        # 5x latency of ~20ms base = ~100ms, p99 will be higher
        assert post_ramp["latency_p99_ms"].mean() > 50

    def test_event_mode_no_healthy_pre_phase(self):
        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=1)
        scenario = DegradationScenario(start, end, event_mode=True, ramp_minutes=5)

        assert scenario.deploy_start == start

    def test_standalone_mode_unchanged(self):
        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=12)
        scenario = DegradationScenario(start, end)

        expected_start = start + timedelta(seconds=12 * 3600 * 0.65)
        assert abs((scenario.deploy_start - expected_start).total_seconds()) < 1


class TestMemoryLeakScenario:
    def test_latency_increases_over_time(self):
        start = datetime(2026, 3, 1, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=48)
        scenario = MemoryLeakScenario(start, end, growth_rate=0.01)

        chunks = list(scenario.generate(resolution_seconds=60))
        df = raw_chunk_to_df(chunks)
        api = df[(df["service"] == "api") & (df["host"] == "host1")]

        early = api[api["timestamp"] < start + timedelta(hours=6)]
        late = api[
            (api["timestamp"] >= start + timedelta(hours=40))
            & (api["timestamp"] < start + timedelta(hours=47))
        ]

        assert late["latency_p99_ms"].mean() > early["latency_p99_ms"].mean() * 2

    def test_memory_grows_over_time(self):
        start = datetime(2026, 3, 1, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=48)
        scenario = MemoryLeakScenario(start, end, growth_rate=0.01)

        chunks = list(scenario.generate(resolution_seconds=60))
        df = raw_chunk_to_df(chunks)
        api = df[(df["service"] == "api") & (df["host"] == "host1")]

        early = api[api["timestamp"] < start + timedelta(hours=6)]
        late = api[api["timestamp"] >= start + timedelta(hours=40)]

        assert late["memory_bytes"].mean() > early["memory_bytes"].mean()

    def test_crash_at_end_spikes_errors(self):
        start = datetime(2026, 3, 1, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=24)
        scenario = MemoryLeakScenario(start, end, crash_at_end=True)

        chunks = list(scenario.generate(resolution_seconds=60))
        df = raw_chunk_to_df(chunks)
        api = df[(df["service"] == "api") & (df["host"] == "host1")]

        final_hour = api[api["timestamp"] >= end - timedelta(hours=1)]
        assert final_hour["error_rate"].mean() > 0.3

    def test_raw_chunk_valid(self):
        start = datetime(2026, 3, 1, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=2)
        scenario = MemoryLeakScenario(start, end)

        chunks = list(scenario.generate(resolution_seconds=30))
        for chunk in chunks:
            validate_raw_chunk(chunk)


class TestTrafficSpikeScenario:
    def test_throughput_spikes_in_rate_limit_mode(self):
        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=2)
        scenario = TrafficSpikeScenario(
            start,
            end,
            spike_multiplier=5.0,
            error_mode="rate_limit",
        )

        chunks = list(scenario.generate(resolution_seconds=30))
        df = raw_chunk_to_df(chunks)
        api = df[(df["service"] == "api") & (df["host"] == "host1")]

        assert api["request_count"].max() > 300

    def test_overload_mode_increases_latency(self):
        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=2)
        scenario = TrafficSpikeScenario(
            start,
            end,
            spike_multiplier=5.0,
            error_mode="overload",
        )

        chunks = list(scenario.generate(resolution_seconds=30))
        df = raw_chunk_to_df(chunks)
        api = df[(df["service"] == "api") & (df["host"] == "host1")]

        # In overload mode, latency should spike significantly
        assert api["latency_p99_ms"].max() > 100  # well above 20ms base

    def test_rate_limit_mode_keeps_latency_low(self):
        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=2)
        scenario = TrafficSpikeScenario(
            start,
            end,
            spike_multiplier=5.0,
            error_mode="rate_limit",
        )

        chunks = list(scenario.generate(resolution_seconds=30))
        df = raw_chunk_to_df(chunks)
        api = df[(df["service"] == "api") & (df["host"] == "host1")]

        # Rate limit mode: latency stays reasonable (base ~20ms, slight increase)
        assert api["latency_median_ms"].max() < 200

    def test_raw_chunk_valid(self):
        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=1)
        scenario = TrafficSpikeScenario(start, end)

        chunks = list(scenario.generate(resolution_seconds=30))
        for chunk in chunks:
            validate_raw_chunk(chunk)


class TestStepChangeScenario:
    def test_latency_shifts_to_new_level(self):
        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=4)
        scenario = StepChangeScenario(start, end, latency_multiplier=2.0, ramp_minutes=5)

        chunks = list(scenario.generate(resolution_seconds=30))
        df = raw_chunk_to_df(chunks)
        api = df[(df["service"] == "api") & (df["host"] == "host1")]

        post_ramp = api[api["timestamp"] >= start + timedelta(minutes=10)]
        # 2x of ~20ms base → median ~40ms, p99 higher
        assert post_ramp["latency_median_ms"].mean() > 25

    def test_throughput_shifts_to_new_level(self):
        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=4)
        scenario = StepChangeScenario(start, end, throughput_multiplier=0.7, ramp_minutes=2)

        chunks = list(scenario.generate(resolution_seconds=30))
        df = raw_chunk_to_df(chunks)
        api = df[(df["service"] == "api") & (df["host"] == "host1")]

        post_ramp = api[api["timestamp"] >= start + timedelta(minutes=5)]
        assert post_ramp["request_count"].mean() < 80

    def test_raw_chunk_valid(self):
        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=1)
        scenario = StepChangeScenario(start, end)

        chunks = list(scenario.generate(resolution_seconds=30))
        for chunk in chunks:
            validate_raw_chunk(chunk)


class TestPolskaScenario:
    def test_raw_chunk_valid(self):
        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=4)
        scenario = PolskaScenario(start, end)

        chunks = list(scenario.generate(resolution_seconds=30))
        for chunk in chunks:
            validate_raw_chunk(chunk)

    def test_throughput_varies_with_contour(self):
        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=4)
        scenario = PolskaScenario(start, end)

        chunks = list(scenario.generate(resolution_seconds=30))
        df = raw_chunk_to_df(chunks)
        api = df[(df["service"] == "api") & (df["host"] == "host1")]

        assert api["request_count"].std() > 5.0

    def test_latency_anticorrelated_with_throughput(self):
        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=4)
        scenario = PolskaScenario(start, end)

        chunks = list(scenario.generate(resolution_seconds=60))
        df = raw_chunk_to_df(chunks)
        api = df[(df["service"] == "api") & (df["host"] == "host1")]

        corr = api["request_count"].corr(api["latency_p99_ms"])
        assert corr < 0
