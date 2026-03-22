"""Cross-backend validation tests — verify all backends derive from the same raw truth."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest
from slo_generator.generator_config import GeneratorConfig
from slo_generator.raw import RawChunk
from slo_generator.scenarios.healthy import HealthyScenario
from slo_generator.shapers.influxdb import InfluxDBShaper
from slo_generator.shapers.prometheus import PrometheusShaper
from slo_generator.shapers.timescaledb import TimescaleDBShaper


def _generate_deterministic_chunk() -> tuple[RawChunk, GeneratorConfig]:
    """Generate 5 minutes of healthy data at 1s resolution, deterministic (seed=42, jitter=0)."""
    config = GeneratorConfig(seed=42, jitter_pct=0.0, scrape_interval_s=15)
    start = datetime(2026, 3, 20, 12, 0, 0, tzinfo=UTC)
    end = start + timedelta(minutes=5)
    scenario = HealthyScenario(start, end, config=config)
    chunks = list(scenario.generate(resolution_seconds=1))
    combined: RawChunk = []
    for c in chunks:
        combined.extend(c)
    return combined, config


def _exact_p99(raw_chunk: RawChunk) -> float:
    """Compute exact p99 from all raw latencies."""
    all_latencies = []
    for s in raw_chunk:
        all_latencies.extend(s.latencies_ms)
    return float(np.percentile(all_latencies, 99))


def _total_requests(raw_chunk: RawChunk) -> int:
    """Total request count from raw data."""
    return sum(s.request_count for s in raw_chunk)


class TestCrossBackendConsistency:
    """Verify all 3 backends produce consistent results from the same raw data."""

    def test_influxdb_latency_count_matches_raw(self):
        raw_chunk, _ = _generate_deterministic_chunk()
        shaper = InfluxDBShaper()
        shaped = list(shaper.shape(raw_chunk))
        df = pd.concat(shaped)

        latency_rows = df[df["measurement"] == "http_request_latency"]
        assert len(latency_rows) == _total_requests(raw_chunk)

    def test_timescaledb_latency_count_matches_raw(self):
        raw_chunk, _ = _generate_deterministic_chunk()
        shaper = TimescaleDBShaper()
        shaped = list(shaper.shape(raw_chunk))

        latency_df = next(df for df in shaped if "latency_ms" in df.columns)
        assert len(latency_df) == _total_requests(raw_chunk)

    def test_influxdb_exact_p99_matches_raw(self):
        raw_chunk, _ = _generate_deterministic_chunk()
        exact_p99 = _exact_p99(raw_chunk)

        shaper = InfluxDBShaper()
        shaped = list(shaper.shape(raw_chunk))
        df = pd.concat(shaped)
        latency_rows = df[df["measurement"] == "http_request_latency"]
        influx_p99 = float(np.percentile(latency_rows["value"].values, 99))

        assert influx_p99 == exact_p99

    def test_timescaledb_exact_p99_matches_raw(self):
        raw_chunk, _ = _generate_deterministic_chunk()
        exact_p99 = _exact_p99(raw_chunk)

        shaper = TimescaleDBShaper()
        shaped = list(shaper.shape(raw_chunk))
        latency_df = next(df for df in shaped if "latency_ms" in df.columns)
        tsdb_p99 = float(np.percentile(latency_df["latency_ms"].values, 99))

        assert tsdb_p99 == exact_p99

    def test_influxdb_p99_equals_timescaledb_p99(self):
        raw_chunk, _ = _generate_deterministic_chunk()

        influx_shaped = list(InfluxDBShaper().shape(raw_chunk))
        influx_df = pd.concat(influx_shaped)
        influx_lats = influx_df[influx_df["measurement"] == "http_request_latency"]["value"].values
        influx_p99 = float(np.percentile(influx_lats, 99))

        tsdb_shaped = list(TimescaleDBShaper().shape(raw_chunk))
        tsdb_lats = next(df for df in tsdb_shaped if "latency_ms" in df.columns)[
            "latency_ms"
        ].values
        tsdb_p99 = float(np.percentile(tsdb_lats, 99))

        assert influx_p99 == tsdb_p99

    def test_prometheus_p99_approximates_exact(self):
        """Prometheus histogram_quantile is approximate — should be within ~20% of exact."""
        raw_chunk, config = _generate_deterministic_chunk()

        # Pick one (service, host) pair for consistent comparison
        target_service = raw_chunk[0].service
        target_host = raw_chunk[0].host
        filtered = [s for s in raw_chunk if s.service == target_service and s.host == target_host]
        all_lats = []
        for s in filtered:
            all_lats.extend(s.latencies_ms)
        exact_p99 = float(np.percentile(all_lats, 99))

        shaper = PrometheusShaper(config=config)
        shaped = list(shaper.shape(raw_chunk))
        df = pd.concat(shaped)

        # Get histogram buckets for the same service/host at the last scrape
        buckets = df[
            (df["metric"] == "http_request_duration_seconds_bucket")
            & (df["service"] == target_service)
            & (df["host"] == target_host)
        ]
        if len(buckets) == 0:
            pytest.skip("no histogram buckets produced")

        last_ts = buckets["timestamp"].max()
        last_buckets = buckets[buckets["timestamp"] == last_ts].copy()
        last_buckets = last_buckets.sort_values("le")

        # Separate finite and +Inf buckets
        le_float = last_buckets["le"].astype(float)
        finite_mask = le_float != float("inf")
        le_values = le_float[finite_mask].values
        counts = last_buckets[finite_mask]["value"].astype(float).values
        inf_count = float(last_buckets[~finite_mask]["value"].iloc[0])
        target = 0.99 * inf_count

        prom_p99_seconds = le_values[-1]
        for i in range(len(counts)):
            if counts[i] >= target:
                if i == 0:
                    prom_p99_seconds = le_values[0]
                else:
                    lower_count = counts[i - 1]
                    lower_bound = le_values[i - 1]
                    upper_bound = le_values[i]
                    denom = counts[i] - lower_count
                    if denom > 0:
                        fraction = (target - lower_count) / denom
                        prom_p99_seconds = lower_bound + fraction * (upper_bound - lower_bound)
                    else:
                        prom_p99_seconds = upper_bound
                break

        prom_p99_ms = prom_p99_seconds * 1000.0

        # Prometheus histogram_quantile is approximate due to bucket interpolation
        ratio = prom_p99_ms / exact_p99
        assert 0.80 < ratio < 1.20, (
            f"prometheus p99 ({prom_p99_ms:.2f}ms) not within 20% "
            f"of exact ({exact_p99:.2f}ms), ratio={ratio:.3f}"
        )

    def test_all_backends_same_total_request_count(self):
        raw_chunk, config = _generate_deterministic_chunk()
        total = _total_requests(raw_chunk)

        # InfluxDB: count latency rows
        influx_shaped = list(InfluxDBShaper().shape(raw_chunk))
        influx_df = pd.concat(influx_shaped)
        influx_lat_count = len(influx_df[influx_df["measurement"] == "http_request_latency"])

        # TimescaleDB: count latency rows
        tsdb_shaped = list(TimescaleDBShaper().shape(raw_chunk))
        tsdb_lat_df = next(df for df in tsdb_shaped if "latency_ms" in df.columns)
        tsdb_lat_count = len(tsdb_lat_df)

        # Prometheus: total count from _count metric at last scrape
        prom_shaped = list(PrometheusShaper(config=config).shape(raw_chunk))
        prom_df = pd.concat(prom_shaped)
        count_rows = prom_df[prom_df["metric"] == "http_request_duration_seconds_count"]
        # Sum across all service/host at the last scrape
        last_ts = count_rows["timestamp"].max()
        prom_total = int(count_rows[count_rows["timestamp"] == last_ts]["value"].sum())

        assert influx_lat_count == total
        assert tsdb_lat_count == total
        # Prometheus count is cumulative at last scrape — may miss trailing seconds
        # between last scrape and end of window (up to scrape_interval - 1 seconds)
        assert prom_total <= total
        assert prom_total >= total * 0.90


class TestJitterBehavior:
    def test_zero_jitter_deterministic(self):
        """Two runs with jitter=0 and same seed produce identical output."""
        chunk1, _ = _generate_deterministic_chunk()
        chunk2, _ = _generate_deterministic_chunk()

        assert len(chunk1) == len(chunk2)
        for s1, s2 in zip(chunk1, chunk2, strict=False):
            assert s1.request_count == s2.request_count
            assert s1.error_count == s2.error_count
            assert s1.latencies_ms == s2.latencies_ms
            assert s1.cpu_percent == s2.cpu_percent
            assert s1.memory_bytes == s2.memory_bytes

    def test_jitter_differs_from_no_jitter(self):
        """With jitter>0, values differ from jitter=0 run."""
        no_jitter, _ = _generate_deterministic_chunk()

        config_jitter = GeneratorConfig(seed=42, jitter_pct=0.05, scrape_interval_s=15)
        start = datetime(2026, 3, 20, 12, 0, 0, tzinfo=UTC)
        end = start + timedelta(minutes=5)
        scenario = HealthyScenario(start, end, config=config_jitter)
        chunks = list(scenario.generate(resolution_seconds=1))
        jittered: RawChunk = []
        for c in chunks:
            jittered.extend(c)

        # At least some values should differ
        diff_count = sum(
            1
            for s1, s2 in zip(no_jitter, jittered, strict=False)
            if s1.request_count != s2.request_count
        )
        assert diff_count > 0

    def test_different_seeds_differ(self):
        """Different seeds produce different outputs."""
        config1 = GeneratorConfig(seed=42, jitter_pct=0.0)
        config2 = GeneratorConfig(seed=99, jitter_pct=0.0)

        start = datetime(2026, 3, 20, 12, 0, 0, tzinfo=UTC)
        end = start + timedelta(minutes=5)

        s1 = HealthyScenario(start, end, config=config1)
        s2 = HealthyScenario(start, end, config=config2)

        chunks1: RawChunk = []
        for c in s1.generate(resolution_seconds=1):
            chunks1.extend(c)

        chunks2: RawChunk = []
        for c in s2.generate(resolution_seconds=1):
            chunks2.extend(c)

        # At least some latencies should differ
        diff_count = sum(
            1 for a, b in zip(chunks1, chunks2, strict=False) if a.latencies_ms != b.latencies_ms
        )
        assert diff_count > 0
