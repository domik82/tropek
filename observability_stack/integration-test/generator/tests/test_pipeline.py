"""Tests for the pipeline wiring."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
from slo_generator.composer import TimelineComposer
from slo_generator.pipeline import run_pipeline
from slo_generator.scenarios.healthy import HealthyScenario


class TestPipeline:
    def test_csv_roundtrip(self, tmp_path: Path):
        """Scenario → RawShaper → CSVAdapter → readable CSV."""
        start = datetime(2026, 3, 20, 12, 0, 0, tzinfo=UTC)
        end = start + timedelta(minutes=5)
        scenario = HealthyScenario(start, end)

        run_pipeline(
            scenario=scenario,
            backends=["csv"],
            output_dir=tmp_path,
            scenario_name="healthy",
        )

        csv_path = tmp_path / "healthy.csv"
        assert csv_path.exists()
        df = pd.read_csv(csv_path)
        assert len(df) > 0
        assert "request_count" in df.columns

    def test_prometheus_pipeline_produces_om_file(self, tmp_path: Path):
        """Scenario → PrometheusShaper → PrometheusAdapter → .om file."""
        start = datetime(2026, 3, 20, 12, 0, 0, tzinfo=UTC)
        end = start + timedelta(minutes=5)
        scenario = HealthyScenario(start, end)

        run_pipeline(
            scenario=scenario,
            backends=["prometheus"],
            output_dir=tmp_path,
            scenario_name="healthy",
        )

        om_path = tmp_path / "healthy_metrics.om"
        assert om_path.exists()
        content = om_path.read_text()
        assert "# EOF" in content
        assert "http_requests_total" in content


class TestTimelinePipeline:
    def test_timeline_csv_roundtrip(self, tmp_path: Path):
        """TimelineComposer -> RawShaper -> CSVAdapter -> readable CSV."""
        yaml_content = """
timeline:
  start: "2026-03-20T00:00:00Z"
  duration: 2h
  resolution: 30s
  events:
    - type: outage
      at: 1h
      duration: 20m
"""
        yaml_path = tmp_path / "timeline.yaml"
        yaml_path.write_text(yaml_content)

        composer = TimelineComposer.from_yaml(yaml_path)
        results = run_pipeline(
            scenario=composer,
            backends=["csv"],
            output_dir=tmp_path,
            scenario_name="timeline",
            resolution_seconds=composer.config.resolution_seconds,
        )

        assert results["csv"] is True
        csv_path = tmp_path / "timeline.csv"
        assert csv_path.exists()
        df = pd.read_csv(csv_path)
        assert len(df) > 0

    def test_timeline_prometheus_pipeline(self, tmp_path: Path):
        """TimelineComposer -> PrometheusShaper -> PrometheusAdapter -> .om file."""
        yaml_content = """
timeline:
  start: "2026-03-20T00:00:00Z"
  duration: 2h
  resolution: 30s
  events:
    - type: step_change
      at: 30m
      duration: 30m
      params:
        latency_multiplier: 2.0
"""
        yaml_path = tmp_path / "timeline.yaml"
        yaml_path.write_text(yaml_content)

        composer = TimelineComposer.from_yaml(yaml_path)
        results = run_pipeline(
            scenario=composer,
            backends=["prometheus"],
            output_dir=tmp_path,
            scenario_name="timeline",
            resolution_seconds=composer.config.resolution_seconds,
        )

        assert results["prometheus"] is True
        om_path = tmp_path / "timeline_metrics.om"
        assert om_path.exists()
        content = om_path.read_text()
        assert "# EOF" in content
        assert "http_requests_total" in content
