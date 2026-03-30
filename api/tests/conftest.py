"""Shared pytest fixtures for all test modules."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from app.modules.quality_gate.engine.slo_models import SLO
from app.modules.quality_gate.engine.slo_parser import build_slo

_DATA_DIR = Path(__file__).parent / 'data'


@pytest.fixture
def slo_fixture():
    """Fixture: load an SLO YAML file from tests/data/slo/ and return a validated SLO model."""

    def _load(name: str) -> SLO:
        path = _DATA_DIR / 'slo' / name
        if not path.exists():
            available = sorted(f.name for f in (_DATA_DIR / 'slo').glob('*.yaml'))
            raise FileNotFoundError(f'SLO fixture {name!r} not found. Available: {available}')
        data: dict[str, Any] = yaml.safe_load(path.read_text(encoding='utf-8'))
        return build_slo(
            objectives=data.get('objectives', []),
            total_score_pass_threshold=data.get('total_score', {}).get('pass_threshold', 90.0),
            total_score_warning_threshold=data.get('total_score', {}).get('warning_threshold', 75.0),
            comparison=data.get('comparison', {}),
        )

    return _load


@pytest.fixture
def result_data():
    """Fixture: load a result file from tests/data/results/ by filename."""

    def _load(name: str) -> str:
        path = _DATA_DIR / 'results' / name
        if not path.exists():
            available = sorted(f.name for f in (_DATA_DIR / 'results').glob('*'))
            raise FileNotFoundError(f'Result fixture {name!r} not found. Available: {available}')
        return path.read_text(encoding='utf-8')

    return _load
