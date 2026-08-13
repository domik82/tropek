"""Tests for the metric-name derivation used by SLO objective validation.

Rows are constructed unsaved — ``build_indicator_keys`` reads columns only, so these
need no session. Using the real ``SLIDefinition`` rather than a stand-in means the
tests fail if a column is renamed or retyped out from under the derivation.
"""

from __future__ import annotations

import pytest
from tropek.db.models import SLIDefinition
from tropek.modules.sli_registry.keys import build_aggregated_templates, build_indicator_keys


def test_raw_mode_keys_are_indicator_names() -> None:
    sli_def = SLIDefinition(
        name='vm-sli',
        mode='raw',
        indicators={'cpu': 'rate(cpu[5m])', 'mem': 'mem_bytes'},
        methods=None,
    )
    assert build_indicator_keys(sli_def) == {'cpu', 'mem'}


def test_aggregated_multi_indicator_keys_are_cross_product() -> None:
    sli_def = SLIDefinition(
        name='vm-sli',
        mode='aggregated',
        indicators={'cpu': 'rate(cpu[$interval])', 'mem': 'mem_bytes'},
        methods=['mean', 'max'],
    )
    assert build_indicator_keys(sli_def) == {'cpu.mean', 'cpu.max', 'mem.mean', 'mem.max'}


def test_aggregated_single_template_keys_use_the_sli_name() -> None:
    sli_def = SLIDefinition(
        name='agg-latency-sli',
        mode='aggregated',
        indicators={},
        query_template='http_request_duration_seconds',
        methods=['mean', 'p95'],
    )
    assert build_indicator_keys(sli_def) == {'agg-latency-sli.mean', 'agg-latency-sli.p95'}


def test_aggregated_without_methods_is_rejected() -> None:
    """Aggregated mode has no meaningful key set without methods.

    ``SLIDefinitionCreate`` requires non-empty methods, and both shipped adapters need
    them to produce any result key, so guessing bare indicator names here would predict
    names no evaluation ever produces.
    """
    sli_def = SLIDefinition(
        name='vm-sli',
        mode='aggregated',
        indicators={'cpu': 'rate(cpu[$interval])'},
        methods=None,
    )
    with pytest.raises(ValueError, match='methods is empty'):
        build_indicator_keys(sli_def)


def test_aggregated_templates_key_by_indicator_name() -> None:
    sli_def = SLIDefinition(
        name='vm-sli',
        mode='aggregated',
        indicators={'cpu': 'rate(cpu[$interval])', 'mem': 'mem_bytes'},
        methods=['mean'],
    )
    assert build_aggregated_templates(sli_def) == {'cpu': 'rate(cpu[$interval])', 'mem': 'mem_bytes'}


def test_aggregated_templates_key_single_template_by_sli_name() -> None:
    sli_def = SLIDefinition(
        name='agg-latency-sli',
        mode='aggregated',
        indicators={},
        query_template='http_request_duration_seconds',
        methods=['mean'],
    )
    assert build_aggregated_templates(sli_def) == {'agg-latency-sli': 'http_request_duration_seconds'}


def test_aggregated_templates_without_any_query_is_rejected() -> None:
    """Neither indicators nor query_template means the row cannot be queried at all."""
    sli_def = SLIDefinition(
        name='vm-sli',
        mode='aggregated',
        indicators={},
        query_template=None,
        methods=['mean'],
    )
    with pytest.raises(ValueError, match='no indicators and no query_template'):
        build_aggregated_templates(sli_def)
