"""Tests for EvalCreateParams and related parameter models."""

import uuid
from datetime import UTC, datetime

from app.modules.quality_gate.params import EvalCreateParams


def test_eval_create_params_requires_evaluation_id():
    p = EvalCreateParams(
        evaluation_id=uuid.uuid4(),
        evaluation_name='daily',
        period_start=datetime(2026, 1, 1, tzinfo=UTC),
        period_end=datetime(2026, 1, 2, tzinfo=UTC),
        ingestion_mode='pull',
        asset_snapshot={},
        asset_id=uuid.uuid4(),
        slo_name='my-slo',
    )
    assert p.evaluation_id is not None
