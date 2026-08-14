"""Tests for adapter query-spec construction from an SLI definition."""

from __future__ import annotations

from typing import Any

import pytest
from tropek.db.models import SLIDefinition
from tropek.modules.quality_gate.workflows.execution.evaluation_executor import _build_query_specs
from tropek.modules.sli_registry.keys import build_indicator_keys

RAW_SLI = SLIDefinition(
    name='vm-sli',
    mode='raw',
    indicators={'cpu': 'rate(cpu[5m])', 'mem': 'mem_bytes'},
    query_template=None,
    interval=None,
    methods=None,
)

AGGREGATED_MULTI_INDICATOR_SLI = SLIDefinition(
    name='vm-sli',
    mode='aggregated',
    indicators={'cpu': 'rate(cpu[$interval])', 'mem': 'mem_bytes'},
    query_template=None,
    interval='5m',
    methods=['mean', 'max'],
)

AGGREGATED_SINGLE_TEMPLATE_SLI = SLIDefinition(
    name='agg-latency-sli',
    mode='aggregated',
    indicators={},
    query_template='http_request_duration_seconds',
    interval='1m',
    methods=['mean', 'p95'],
)


def _adapter_result_keys(specs: dict[str, dict[str, Any]]) -> set[str]:
    """Return the metric names an adapter would answer a set of query specs with.

    This mirrors the adapter contract documented on ``AdapterQueryRequest``: a raw spec
    answers one value under the spec key, an aggregated spec answers one value per
    method under ``<spec_key>.<method>``. Both shipped adapters implement exactly this
    (``adapters/prometheus/tropek_prometheus/core/strategies/aggregated.py``,
    ``adapters/mock/tropek_mock/main.py``).
    """
    result_keys: set[str] = set()
    for spec_key, spec in specs.items():
        if spec['mode'] == 'aggregated':
            result_keys.update(f'{spec_key}.{method}' for method in spec['methods'])
        else:
            result_keys.add(spec_key)
    return result_keys


def test_raw_mode_wraps_each_resolved_query() -> None:
    specs = _build_query_specs(RAW_SLI, {'cpu': 'rate(cpu[5m])'})
    assert specs == {'cpu': {'mode': 'raw', 'query': 'rate(cpu[5m])'}}


def test_aggregated_multi_indicator_fans_out_one_spec_per_indicator() -> None:
    specs = _build_query_specs(AGGREGATED_MULTI_INDICATOR_SLI, {})
    assert specs == {
        'cpu': {
            'mode': 'aggregated',
            'query_template': 'rate(cpu[$interval])',
            'interval': '5m',
            'methods': ['mean', 'max'],
        },
        'mem': {
            'mode': 'aggregated',
            'query_template': 'mem_bytes',
            'interval': '5m',
            'methods': ['mean', 'max'],
        },
    }


def test_aggregated_single_template_keys_spec_by_sli_name() -> None:
    specs = _build_query_specs(AGGREGATED_SINGLE_TEMPLATE_SLI, {})
    assert specs == {
        'agg-latency-sli': {
            'mode': 'aggregated',
            'query_template': 'http_request_duration_seconds',
            'interval': '1m',
            'methods': ['mean', 'p95'],
        }
    }


def test_aggregated_without_any_query_is_rejected() -> None:
    """A row with neither indicators nor query_template must fail loudly.

    Without this the spec would carry ``query_template: None`` to the adapter, which
    surfaces as an opaque adapter-side error instead of a bad SLI definition.
    """
    sli_def = SLIDefinition(
        name='broken-sli',
        mode='aggregated',
        indicators={},
        query_template=None,
        interval='1m',
        methods=['mean'],
    )
    with pytest.raises(ValueError, match='no indicators and no query_template'):
        _build_query_specs(sli_def, {})


@pytest.mark.parametrize(
    ('sli_def', 'resolved_queries'),
    [
        (RAW_SLI, {'cpu': 'rate(cpu[5m])', 'mem': 'mem_bytes'}),
        (AGGREGATED_MULTI_INDICATOR_SLI, {}),
        (AGGREGATED_SINGLE_TEMPLATE_SLI, {}),
    ],
    ids=['raw', 'aggregated-multi-indicator', 'aggregated-single-template'],
)
def test_predicted_objective_keys_match_adapter_result_keys(
    sli_def: SLIDefinition,
    resolved_queries: dict[str, str],
) -> None:
    """The names SLO creation accepts must be exactly the names an evaluation produces.

    ``build_indicator_keys`` gates which ``objective.sli`` values a POST /slo-definitions
    will accept; ``_build_query_specs`` decides which result keys the adapter actually
    returns. If they drift, SLO creation either rejects a valid objective or accepts one
    that can never receive a value and silently scores as missing.
    """
    predicted = build_indicator_keys(sli_def)
    produced = _adapter_result_keys(_build_query_specs(sli_def, resolved_queries))
    assert predicted == produced
