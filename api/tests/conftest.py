"""Shared pytest fixtures for all test modules.

Test data files live in tests/data/:
  slo/      — SLO YAML definitions (human-readable, IDE-validated)
  results/  — Sample result files (CSV, JMeter XML, etc.)

Usage in tests — inject the fixture, call it like a function:

    def test_something(slo_data):
        yaml = slo_data("minimal.yaml")

    def test_results(result_data):
        csv = result_data("sample.csv")
"""

from __future__ import annotations

from pathlib import Path

import pytest

_DATA_DIR = Path(__file__).parent / "data"


@pytest.fixture()
def slo_data():
    """Fixture: load an SLO YAML file from tests/data/slo/ by filename."""

    def _load(name: str) -> str:
        path = _DATA_DIR / "slo" / name
        if not path.exists():
            available = sorted(f.name for f in (_DATA_DIR / "slo").glob("*.yaml"))
            raise FileNotFoundError(f"SLO fixture {name!r} not found. Available: {available}")
        return path.read_text(encoding="utf-8")

    return _load


@pytest.fixture()
def result_data():
    """Fixture: load a result file from tests/data/results/ by filename."""

    def _load(name: str) -> str:
        path = _DATA_DIR / "results" / name
        if not path.exists():
            available = sorted(f.name for f in (_DATA_DIR / "results").glob("*"))
            raise FileNotFoundError(f"Result fixture {name!r} not found. Available: {available}")
        return path.read_text(encoding="utf-8")

    return _load
