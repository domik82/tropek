"""Shared test helpers and fixtures for all test modules.

Test data files live in tests/data/:
  slo/      — SLO YAML definitions (human-readable, IDE-validated)
  results/  — Sample result files (CSV, JMeter XML, etc.)
"""
from __future__ import annotations

from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"


def load_slo(name: str) -> str:
    """Load an SLO YAML file from tests/data/slo/.

    Usage:
        slo_yaml = load_slo("minimal.yaml")
        slo_yaml = load_slo("full_evaluation.yaml")
    """
    path = DATA_DIR / "slo" / name
    if not path.exists():
        available = [f.name for f in (DATA_DIR / "slo").glob("*.yaml")]
        raise FileNotFoundError(
            f"SLO fixture {name!r} not found. Available: {available}"
        )
    return path.read_text(encoding="utf-8")


def load_result(name: str) -> str:
    """Load a result file from tests/data/results/.

    Usage:
        csv_content = load_result("sample.csv")
        xml_content = load_result("jmeter_sample.xml")
    """
    path = DATA_DIR / "results" / name
    if not path.exists():
        available = [f.name for f in (DATA_DIR / "results").glob("*")]
        raise FileNotFoundError(
            f"Result fixture {name!r} not found. Available: {available}"
        )
    return path.read_text(encoding="utf-8")
