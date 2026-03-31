"""Tests for SLO registry Pydantic param models."""

from __future__ import annotations

from app.modules.slo_registry.params import SLOCreateParams, SLOObjectiveParams


def test_slo_create_params_minimal() -> None:
    params = SLOCreateParams(
        name='perf-slo',
        objectives=[
            SLOObjectiveParams(sli='response_time'),
        ],
    )
    assert params.name == 'perf-slo'
    assert params.total_score_pass_threshold == 90.0
    assert params.total_score_warning_threshold == 75.0
    assert params.tags == {}
    assert params.variables == {}
    assert params.kind == 'standard'


def test_slo_create_params_full() -> None:
    params = SLOCreateParams(
        name='perf-slo',
        objectives=[
            SLOObjectiveParams(
                sli='response_time',
                display_name='Response Time',
                weight=2,
                key_sli=True,
                pass_threshold=['<600'],
                warning_threshold=['<800'],
            ),
        ],
        total_score_pass_threshold=95.0,
        total_score_warning_threshold=80.0,
        display_name='Performance SLO',
        notes='Initial version',
        author='test-user',
        tags={'env': 'prod'},
        variables={'region': 'us-east'},
        kind='standard',
        sli_name='system-sli',
        sli_version=2,
    )
    assert params.objectives[0].weight == 2
    assert params.objectives[0].key_sli is True
    assert params.display_name == 'Performance SLO'
    assert params.tags == {'env': 'prod'}


def test_slo_objective_params_defaults() -> None:
    obj = SLOObjectiveParams(sli='throughput')
    assert obj.display_name is None
    assert obj.weight == 1
    assert obj.key_sli is False
    assert obj.pass_threshold == []
    assert obj.warning_threshold == []
