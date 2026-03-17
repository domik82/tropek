"""Unit tests for the scenario CSV generator."""

from __future__ import annotations

import tempfile
from pathlib import Path

from generate import generate_scenario, load_scenario


def test_load_scenario() -> None:
    scenario = load_scenario(Path("scenarios/stable.yaml"))
    assert scenario["name"] == "stable"
    assert "metrics" in scenario
    assert scenario["interval_minutes"] > 0


def test_generate_stable_creates_csv_per_namespace() -> None:
    scenario = load_scenario(Path("scenarios/stable.yaml"))
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)
        generate_scenario(scenario, out_dir)
        # Should create a directory per namespace
        for ns in scenario["namespaces"]:
            csv_path = out_dir / ns / "metrics.csv"
            assert csv_path.exists(), f"missing {csv_path}"
            with csv_path.open() as f:
                header = f.readline().strip()
                assert "timestamp" in header
                assert "metric_name" in header
                assert "value" in header


def test_generate_is_deterministic() -> None:
    scenario = load_scenario(Path("scenarios/stable.yaml"))
    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        generate_scenario(scenario, Path(d1))
        generate_scenario(scenario, Path(d2))
        for ns in scenario["namespaces"]:
            f1 = Path(d1) / ns / "metrics.csv"
            f2 = Path(d2) / ns / "metrics.csv"
            assert f1.read_text() == f2.read_text()
