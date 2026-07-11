import uuid
from datetime import UTC, datetime

from tropek.modules.change_points.repository import ChangePointKey
from tropek.modules.change_points.schemas import ChangePointMarker
from tropek.modules.quality_gate.schemas.trend import TrendColumnFragment, TrendFragmentPoint
from tropek.modules.quality_gate.workflows.presentation.trend_assembler import (
    TrendRow,
    assemble_slo_trends,
    build_trend_fragment,
)

SLO_EVAL_ID = uuid.UUID('22222222-2222-2222-2222-222222222222')


def test_build_trend_fragment_normalizes_score_against_total_weight():
    fragment = build_trend_fragment(
        slo_evaluation_id=SLO_EVAL_ID,
        slo_name='cx-dec',
        period_start=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
        period_end=datetime(2026, 1, 1, 13, 0, 0, tzinfo=UTC),
        evaluation_name='dec',
        total_weight=2.0,
        rows=[
            TrendRow(metric='cpu_time', value=1.5, raw_score=1.0, result='pass', compared_value=1.0, targets=None),
        ],
    )
    # raw_score 1.0 / total_weight 2.0 * 100 = 50.0
    assert fragment.points[0].score == 50.0
    assert fragment.points[0].baseline == 1.0


def test_build_trend_fragment_scores_zero_when_total_weight_zero():
    fragment = build_trend_fragment(
        slo_evaluation_id=SLO_EVAL_ID,
        slo_name='s',
        period_start=datetime(2026, 1, 1, tzinfo=UTC),
        period_end=None,
        evaluation_name='e',
        total_weight=0.0,
        rows=[TrendRow(metric='m', value=1.0, raw_score=5.0, result='pass', compared_value=None, targets=None)],
    )
    assert fragment.points[0].score == 0


def test_assemble_groups_by_metric_and_orders_by_time_then_eval_name():
    def make(metric, period_start, evaluation_name, slo_eval_id):
        return TrendColumnFragment(
            slo_evaluation_id=slo_eval_id,
            slo_name='cx-dec',
            period_start=period_start,
            period_end=None,
            evaluation_name=evaluation_name,
            points=[
                TrendFragmentPoint(metric=metric, value=1.0, score=10.0, result='pass', baseline=None, targets=None)
            ],
        )

    older = make('cpu_time', datetime(2026, 1, 1, 12, 0, tzinfo=UTC), 'dec', uuid.uuid4())
    newer = make('cpu_time', datetime(2026, 1, 2, 12, 0, tzinfo=UTC), 'dec', uuid.uuid4())
    result = assemble_slo_trends([newer, older], change_point_lookup=None)
    assert list(result.keys()) == ['cpu_time']
    timestamps = [point.timestamp for point in result['cpu_time']]
    assert timestamps == [datetime(2026, 1, 1, 12, 0, tzinfo=UTC), datetime(2026, 1, 2, 12, 0, tzinfo=UTC)]
    assert result['cpu_time'][0].eval_id == older.slo_evaluation_id
    assert result['cpu_time'][0].evaluation_name == 'dec'


def test_assemble_overlays_change_point_from_lookup():
    # The lookup value is duck-typed: the assembler reads .direction /
    # .change_relative_pct / .transition / .change_absolute and rebuilds a
    # ChangePointMarker. Both ChangePoint DB entities (real path) and
    # ChangePointMarker (this test) expose those attributes.
    period_start = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    fragment = TrendColumnFragment(
        slo_evaluation_id=SLO_EVAL_ID,
        slo_name='cx-dec',
        period_start=period_start,
        period_end=None,
        evaluation_name='dec',
        points=[
            TrendFragmentPoint(metric='cpu_time', value=1.0, score=10.0, result='pass', baseline=None, targets=None)
        ],
    )
    marker = ChangePointMarker(direction='regression', change_relative_pct=12.0, change_absolute=3.0)
    lookup = {ChangePointKey('cx-dec', 'cpu_time', period_start, None, 'dec'): marker}
    result = assemble_slo_trends([fragment], change_point_lookup=lookup)
    assert result['cpu_time'][0].change_point == marker
