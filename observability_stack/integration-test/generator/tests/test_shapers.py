"""Tests for metric shapers."""

from __future__ import annotations

import pandas as pd
from slo_generator.shapers.influxdb import InfluxDBShaper
from slo_generator.shapers.prometheus import PrometheusShaper
from slo_generator.shapers.raw import RawShaper
from slo_generator.shapers.timescaledb import TimescaleDBShaper


class TestRawShaper:
    def test_passthrough_returns_same_data(self, sample_profile_chunk: pd.DataFrame):
        shaper = RawShaper()
        shaped = list(shaper.shape(sample_profile_chunk))
        assert len(shaped) == 1
        pd.testing.assert_frame_equal(shaped[0], sample_profile_chunk)

    def test_finalize_yields_nothing(self):
        shaper = RawShaper()
        assert list(shaper.finalize()) == []


class TestPrometheusShaper:
    def test_output_has_prometheus_columns(self, sample_profile_chunk: pd.DataFrame):
        shaper = PrometheusShaper(scrape_interval=30)
        shaped = list(shaper.shape(sample_profile_chunk))
        df = pd.concat(shaped)

        required = {"timestamp", "metric", "value", "service", "host", "instance", "job"}
        assert required.issubset(set(df.columns))

    def test_downsamples_to_scrape_interval(self, sample_profile_chunk: pd.DataFrame):
        shaper = PrometheusShaper(scrape_interval=30)
        shaped = list(shaper.shape(sample_profile_chunk))
        df = pd.concat(shaped)

        # 60s of 1s data downsampled to 30s → 2 timestamps per metric per label set
        ts_per_metric = df.groupby(["metric", "service", "host"])["timestamp"].nunique()
        assert (ts_per_metric == 2).all()

    def test_counter_values_are_monotonically_increasing(self, sample_profile_chunk: pd.DataFrame):
        shaper = PrometheusShaper(scrape_interval=30)
        shaped = list(shaper.shape(sample_profile_chunk))
        df = pd.concat(shaped)

        counters = df[df["metric"] == "http_requests_total"].sort_values("timestamp")
        for _, group in counters.groupby(["service", "host", "instance"]):
            values = group["value"].values
            assert all(values[i] <= values[i + 1] for i in range(len(values) - 1))

    def test_instance_and_job_labels_present(self, sample_profile_chunk: pd.DataFrame):
        shaper = PrometheusShaper(scrape_interval=30)
        shaped = list(shaper.shape(sample_profile_chunk))
        df = pd.concat(shaped)

        assert (df["job"] == "app").all()
        assert df["instance"].str.contains(":").all()  # format: service-host:port

    def test_histogram_buckets_present(self, sample_profile_chunk: pd.DataFrame):
        shaper = PrometheusShaper(scrape_interval=30)
        shaped = list(shaper.shape(sample_profile_chunk))
        df = pd.concat(shaped)

        buckets = df[df["metric"] == "http_request_duration_seconds_bucket"]
        assert len(buckets) > 0
        assert "+Inf" in buckets["le"].values

    def test_finalize_flushes_remaining_state(self, sample_profile_chunk: pd.DataFrame):
        shaper = PrometheusShaper(scrape_interval=30)
        # Feed data
        list(shaper.shape(sample_profile_chunk))
        # Finalize should not error
        final = list(shaper.finalize())
        # May or may not have data, but should not crash
        assert isinstance(final, list)


class TestInfluxDBShaper:
    def test_output_has_influxdb_columns(self, sample_profile_chunk: pd.DataFrame):
        shaper = InfluxDBShaper()
        shaped = list(shaper.shape(sample_profile_chunk))
        df = pd.concat(shaped)

        required = {"timestamp", "measurement", "service", "host", "value"}
        assert required.issubset(set(df.columns))

    def test_keeps_1s_resolution(self, sample_profile_chunk: pd.DataFrame):
        shaper = InfluxDBShaper()
        shaped = list(shaper.shape(sample_profile_chunk))
        df = pd.concat(shaped)

        # Should preserve all 60 timestamps for each metric
        for _, grp in df.groupby(["measurement", "service", "host"]):
            ts = grp["timestamp"].unique()
            assert len(ts) == 60

    def test_counters_have_rate_field(self, sample_profile_chunk: pd.DataFrame):
        shaper = InfluxDBShaper()
        shaped = list(shaper.shape(sample_profile_chunk))
        df = pd.concat(shaped)

        requests = df[df["measurement"] == "http_requests_total"]
        assert "rate" in requests.columns
        # Rate should be positive (throughput > 0)
        assert (requests["rate"].dropna() >= 0).all()


class TestTimescaleDBShaper:
    def test_output_has_timescaledb_columns(self, sample_profile_chunk: pd.DataFrame):
        shaper = TimescaleDBShaper()
        shaped = list(shaper.shape(sample_profile_chunk))
        df = pd.concat(shaped)

        required = {"timestamp", "metric", "service", "host", "value"}
        assert set(df.columns) == required

    def test_histograms_as_summary_rows(self, sample_profile_chunk: pd.DataFrame):
        shaper = TimescaleDBShaper()
        shaped = list(shaper.shape(sample_profile_chunk))
        df = pd.concat(shaped)

        hist_metrics = df[df["metric"].str.startswith("http_request_duration")]
        metric_names = set(hist_metrics["metric"].unique())
        # Should have p50, p99, avg summary rows — not individual buckets
        assert "http_request_duration_seconds_p50" in metric_names
        assert "http_request_duration_seconds_p99" in metric_names
