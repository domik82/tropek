import uuid
from datetime import UTC, datetime

from app.modules.quality_gate.schemas import (
    BatchPeriod,
    EvaluateBatchRequest,
    EvaluateBatchResponse,
    EvaluateSingleRequest,
    EvaluateSingleResponse,
)


def test_evaluate_single_request_schema():
    req = EvaluateSingleRequest(
        asset_name='checkout-api',
        eval_name='daily-evaluation',
        period_start=datetime(2026, 1, 15, tzinfo=UTC),
        period_end=datetime(2026, 1, 15, 23, 59, 59, tzinfo=UTC),
    )
    assert req.asset_name == 'checkout-api'
    assert req.eval_name == 'daily-evaluation'
    assert req.variables == {}


def test_evaluate_single_response_schema():
    r = EvaluateSingleResponse(
        evaluation_id=uuid.uuid4(),
        slo_evaluation_ids=[uuid.uuid4(), uuid.uuid4()],
    )
    assert len(r.slo_evaluation_ids) == 2


def test_evaluate_batch_request_by_date():
    req = EvaluateBatchRequest(
        mode='by_date',
        asset_name='checkout-api',
        eval_name='daily',
        periods=[
            BatchPeriod(
                period_start=datetime(2026, 1, 15, tzinfo=UTC),
                period_end=datetime(2026, 1, 16, tzinfo=UTC),
            ),
        ],
    )
    assert req.mode == 'by_date'
    assert req.asset_name == 'checkout-api'
    assert req.asset_names is None


def test_evaluate_batch_request_by_asset():
    req = EvaluateBatchRequest(
        mode='by_asset',
        asset_names=['vm-01', 'vm-02'],
        eval_name='post-deploy',
        period_start=datetime(2026, 1, 15, 14, tzinfo=UTC),
        period_end=datetime(2026, 1, 15, 15, tzinfo=UTC),
    )
    assert req.mode == 'by_asset'
    assert len(req.asset_names) == 2


def test_evaluate_batch_response():
    r = EvaluateBatchResponse(
        evaluation_ids=[uuid.uuid4(), uuid.uuid4()],
        slo_evaluation_ids=[uuid.uuid4()],
    )
    assert len(r.evaluation_ids) == 2
