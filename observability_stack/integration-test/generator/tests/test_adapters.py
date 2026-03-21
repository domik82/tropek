"""Tests for adapters (I/O layer)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from slo_generator.adapters.csv import CSVAdapter
from slo_generator.adapters.prometheus import PrometheusAdapter


class TestCSVAdapter:
    def test_writes_dataframe_to_csv_file(self, tmp_path: Path, sample_profile_chunk: pd.DataFrame):
        output = tmp_path / "output.csv"
        with CSVAdapter(output) as adapter:
            adapter.write_chunk(sample_profile_chunk)

        result = pd.read_csv(output)
        assert len(result) == len(sample_profile_chunk)
        assert set(result.columns) == set(sample_profile_chunk.columns)

    def test_appends_multiple_chunks(self, tmp_path: Path, sample_profile_chunk: pd.DataFrame):
        output = tmp_path / "output.csv"
        with CSVAdapter(output) as adapter:
            adapter.write_chunk(sample_profile_chunk)
            adapter.write_chunk(sample_profile_chunk)

        result = pd.read_csv(output)
        assert len(result) == len(sample_profile_chunk) * 2


class TestPrometheusAdapter:
    def _make_shaped_df(self) -> pd.DataFrame:
        """Minimal Prometheus-shaped DataFrame for testing."""
        return pd.DataFrame(
            {
                "timestamp": pd.to_datetime(
                    ["2026-03-20T12:00:00Z", "2026-03-20T12:00:30Z"], utc=True
                ),
                "metric": ["http_requests_total", "http_requests_total"],
                "value": [100.0, 200.0],
                "service": ["frontend", "frontend"],
                "host": ["host1", "host1"],
                "instance": ["frontend-host1:8080", "frontend-host1:8080"],
                "job": ["app", "app"],
                "le": [pd.NA, pd.NA],
                "status_code": ["200", "200"],
            }
        )

    def test_writes_openmetrics_format(self, tmp_path: Path):
        output = tmp_path / "test.om"
        df = self._make_shaped_df()

        with PrometheusAdapter(output) as adapter:
            adapter.write_chunk(df)

        content = output.read_text()
        assert "# TYPE http_requests_total counter" in content
        assert "# EOF" in content

    def test_groups_histogram_by_label_and_timestamp(self, tmp_path: Path):
        ts = pd.to_datetime("2026-03-20T12:00:00Z", utc=True)
        df = pd.DataFrame(
            {
                "timestamp": [ts, ts, ts, ts],
                "metric": [
                    "http_request_duration_seconds_bucket",
                    "http_request_duration_seconds_bucket",
                    "http_request_duration_seconds_sum",
                    "http_request_duration_seconds_count",
                ],
                "value": [50.0, 100.0, 5.0, 100.0],
                "service": ["frontend"] * 4,
                "host": ["host1"] * 4,
                "instance": ["frontend-host1:8080"] * 4,
                "job": ["app"] * 4,
                "le": ["0.1", "+Inf", pd.NA, pd.NA],
                "status_code": [pd.NA] * 4,
            }
        )

        output = tmp_path / "hist.om"
        with PrometheusAdapter(output) as adapter:
            adapter.write_chunk(df)

        lines = output.read_text().splitlines()
        # bucket, sum, count should appear together (not scattered)
        bucket_indices = [i for i, line in enumerate(lines) if "bucket" in line]
        sum_indices = [
            i for i, line in enumerate(lines) if "_sum" in line and not line.startswith("#")
        ]
        count_indices = [
            i for i, line in enumerate(lines) if "_count" in line and not line.startswith("#")
        ]

        if bucket_indices and sum_indices and count_indices:
            # sum and count should come right after last bucket
            assert sum_indices[0] > bucket_indices[-1]
            assert count_indices[0] > sum_indices[0]
