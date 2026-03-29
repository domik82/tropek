"""Tests for quality gate Pydantic param models."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.modules.quality_gate.params import EvalCreateParams


def test_eval_create_params_required_fields() -> None:
    params = EvalCreateParams(
        evaluation_name='nightly',
        period_start=datetime(2026, 3, 15, 10, 0, tzinfo=UTC),
        period_end=datetime(2026, 3, 15, 10, 30, tzinfo=UTC),
        ingestion_mode='pull',
        asset_snapshot={'name': 'vm-01'},
        asset_id=uuid.uuid4(),
        slo_name='perf-slo',
    )
    assert params.evaluation_name == 'nightly'
    assert params.variables == {}


def test_eval_create_params_optional_fields() -> None:
    params = EvalCreateParams(
        evaluation_name='nightly',
        period_start=datetime(2026, 3, 15, 10, 0, tzinfo=UTC),
        period_end=datetime(2026, 3, 15, 10, 30, tzinfo=UTC),
        ingestion_mode='pull',
        asset_snapshot={'name': 'vm-01'},
        asset_id=uuid.uuid4(),
        slo_name='perf-slo',
        slo_version=2,
        adapter_used='prometheus',
        sli_name='system-sli',
        sli_version=1,
        data_source_name='prod-prom',
    )
    assert params.slo_version == 2
    assert params.adapter_used == 'prometheus'
