"""Tests for metric shapers."""

from __future__ import annotations

import pandas as pd
from slo_generator.generator_config import GeneratorConfig
from slo_generator.raw import RawChunk
from slo_generator.shapers.influxdb import InfluxDBShaper
from slo_generator.shapers.prometheus import PrometheusShaper
from slo_generator.shapers.raw import RawShaper
from slo_generator.shapers.timescaledb import TimescaleDBShaper


class TestRawShaper:
    def test_converts_raw_chunk_to_dataframe(self, sample_raw_chunk: RawChunk):
        shaper = RawShaper()
        shaped = list(shaper.shape(sample_raw_chunk))
        assert len(shaped) == 1
        df = shaped[0]
        assert "request_count" in df.columns
        assert len(df) == 60

    def test_finalize_yields_nothing(self):
        shaper = RawShaper()
        assert list(shaper.finalize()) == []


class TestPrometheusShaper:
    def _config_15s(self) -> GeneratorConfig:
        return GeneratorConfig(scrape_interval_s=15)

    def test_output_has_prometheus_columns(self, sample_raw_chunk: RawChunk):
        shaper = PrometheusShaper(config=self._config_15s())
        shaped = list(shaper.shape(sample_raw_chunk))
        df = pd.concat(shaped)

        required = {"timestamp", "metric", "value", "service", "host", "instance", "job"}
        assert required.issubset(set(df.columns))

    def test_emits_at_scrape_intervals(self, sample_raw_chunk: RawChunk):
        shaper = PrometheusShaper(config=self._config_15s())
        shaped = list(shaper.shape(sample_raw_chunk))
        df = pd.concat(shaped)

        # 60s of 1s data at 15s scrape interval → 4 timestamps per metric per label set
        ts_per_metric = df.groupby(["metric", "service", "host"])["timestamp"].nunique()
        assert (ts_per_metric == 4).all()

    def test_counter_values_are_monotonically_increasing(self, sample_raw_chunk: RawChunk):
        shaper = PrometheusShaper(config=self._config_15s())
        shaped = list(shaper.shape(sample_raw_chunk))
        df = pd.concat(shaped)

        counters = df[df["metric"] == "http_requests_total"].sort_values("timestamp")
        for _, group in counters.groupby(["service", "host", "instance"]):
            values = group["value"].values
            assert all(values[i] <= values[i + 1] for i in range(len(values) - 1))

    def test_instance_and_job_labels_present(self, sample_raw_chunk: RawChunk):
        shaper = PrometheusShaper(config=self._config_15s())
        shaped = list(shaper.shape(sample_raw_chunk))
        df = pd.concat(shaped)

        assert (df["job"] == "app").all()
        assert df["instance"].str.contains(":").all()

    def test_histogram_buckets_present(self, sample_raw_chunk: RawChunk):
        shaper = PrometheusShaper(config=self._config_15s())
        shaped = list(shaper.shape(sample_raw_chunk))
        df = pd.concat(shaped)

        buckets = df[df["metric"] == "http_request_duration_seconds_bucket"]
        assert len(buckets) > 0
        assert "+Inf" in buckets["le"].values

    def test_finalize_yields_nothing(self):
        shaper = PrometheusShaper()
        final = list(shaper.finalize())
        assert final == []


class TestInfluxDBShaper:
    def test_output_has_influxdb_columns(self, sample_raw_chunk: RawChunk):
        shaper = InfluxDBShaper()
        shaped = list(shaper.shape(sample_raw_chunk))
        df = pd.concat(shaped)

        required = {"timestamp", "measurement", "service", "host", "value"}
        assert required.issubset(set(df.columns))

    def test_keeps_1s_resolution_for_counters(self, sample_raw_chunk: RawChunk):
        shaper = InfluxDBShaper()
        shaped = list(shaper.shape(sample_raw_chunk))
        df = pd.concat(shaped)

        # Counter measurements should have all 60 timestamps
        requests = df[df["measurement"] == "http_requests_total"]
        assert requests["timestamp"].nunique() == 60

    def test_emits_individual_latency_points(self, sample_raw_chunk: RawChunk):
        shaper = InfluxDBShaper()
        shaped = list(shaper.shape(sample_raw_chunk))
        df = pd.concat(shaped)

        latencies = df[df["measurement"] == "http_request_latency"]
        # 60 seconds * 100 requests = 6000 latency points
        assert len(latencies) == 6000


class TestTimescaleDBShaper:
    def test_emits_metrics_dataframe(self, sample_raw_chunk: RawChunk):
        shaper = TimescaleDBShaper()
        shaped = list(shaper.shape(sample_raw_chunk))

        # Should emit 2 DataFrames: metrics + latencies
        assert len(shaped) == 2

        metrics_df = shaped[0]
        required = {"timestamp", "metric", "service", "host", "value"}
        assert set(metrics_df.columns) == required

    def test_emits_latency_dataframe(self, sample_raw_chunk: RawChunk):
        shaper = TimescaleDBShaper()
        shaped = list(shaper.shape(sample_raw_chunk))

        latency_df = shaped[1]
        required = {"timestamp", "service", "host", "latency_ms"}
        assert set(latency_df.columns) == required
        # 60 seconds * 100 requests = 6000 latency rows
        assert len(latency_df) == 6000

    def test_metrics_include_counters_and_gauges(self, sample_raw_chunk: RawChunk):
        shaper = TimescaleDBShaper()
        shaped = list(shaper.shape(sample_raw_chunk))

        metrics_df = shaped[0]
        metric_names = set(metrics_df["metric"].unique())
        assert "http_requests_total" in metric_names
        assert "http_errors_total" in metric_names
        assert "cpu_usage_percent" in metric_names
        assert "memory_usage_bytes" in metric_names
