"""Tests for the pipeline wiring."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd


class TestPipeline:
    def test_csv_roundtrip(self, tmp_path: Path):
        """Scenario → RawShaper → CSVAdapter → readable CSV."""
        from slo_generator.pipeline import run_pipeline
        from slo_generator.scenarios.healthy import HealthyScenario

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

    def test_prometheus_pipeline_produces_om_file(self, tmp_path: Path):
        """Scenario → PrometheusShaper → PrometheusAdapter → .om file."""
        from slo_generator.pipeline import run_pipeline
        from slo_generator.scenarios.healthy import HealthyScenario

        start = datetime(2026, 3, 20, 12, 0, 0, tzinfo=UTC)
        end = start + timedelta(minutes=5)
        scenario = HealthyScenario(start, end)

        run_pipeline(
            scenario=scenario,
            backends=["prometheus"],
            output_dir=tmp_path,
            scenario_name="healthy",
            prometheus_scrape_interval=30,
        )

        om_path = tmp_path / "healthy_metrics.om"
        assert om_path.exists()
        content = om_path.read_text()
        assert "# EOF" in content
        assert "http_requests_total" in content
