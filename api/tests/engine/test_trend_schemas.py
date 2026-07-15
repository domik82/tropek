import uuid
from datetime import UTC, datetime

from tropek.modules.quality_gate.schemas.evaluations import TrendPoint, TrendTargetEntry, TrendTargets
from tropek.modules.quality_gate.schemas.trend import (
    TREND_FRAGMENT_SCHEMA_VERSION,
    SloTrendsResponse,
    TrendColumnFragment,
    TrendFragmentPoint,
)


def test_trend_column_fragment_round_trips_through_json():
    fragment = TrendColumnFragment(
        slo_evaluation_id=uuid.UUID('11111111-1111-1111-1111-111111111111'),
        slo_name='cx-dec',
        period_start=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
        period_end=datetime(2026, 1, 1, 13, 0, 0, tzinfo=UTC),
        evaluation_name='dec',
        points=[
            TrendFragmentPoint(
                metric='cpu_time',
                value=1.5,
                score=42.0,
                result='pass',
                baseline=1.0,
                targets=TrendTargets(
                    pass_targets=[TrendTargetEntry(criteria='<600', target_value=600.0, violated=False)]
                ),
            )
        ],
    )
    restored = TrendColumnFragment.model_validate_json(fragment.model_dump_json())
    assert restored == fragment
    assert restored.schema_version == TREND_FRAGMENT_SCHEMA_VERSION


def test_slo_trends_response_serializes_as_metric_keyed_map():
    response = SloTrendsResponse(
        root={
            'cpu_time': [
                TrendPoint(
                    timestamp=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
                    value=1.5,
                    score=42.0,
                    eval_id=uuid.UUID('11111111-1111-1111-1111-111111111111'),
                    result='pass',
                    baseline=1.0,
                )
            ]
        }
    )
    dumped = response.model_dump(mode='json')
    assert list(dumped.keys()) == ['cpu_time']
    assert dumped['cpu_time'][0]['value'] == 1.5
