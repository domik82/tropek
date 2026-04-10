"""Tests for SLI registry Pydantic param models."""

from __future__ import annotations

from app.modules.sli_registry.params import SLICreateParams


def test_sli_create_params_minimal() -> None:
    params = SLICreateParams(
        name='system-sli',
        indicators={'response_time': 'avg(http_duration)'},
        adapter_type='prometheus',
    )
    assert params.name == 'system-sli'
    assert params.tags == {}
    assert params.display_name is None
    assert params.comparable_from_version is None


def test_sli_create_params_full() -> None:
    params = SLICreateParams(
        name='system-sli',
        indicators={
            'response_time': 'avg(http_duration)',
            'error_rate': 'sum(http_errors)/sum(http_total)',
        },
        adapter_type='prometheus',
        display_name='System SLI',
        notes='Added error_rate metric',
        author='test-user',
        tags={'team': 'platform'},
        comparable_from_version=1,
    )
    assert len(params.indicators) == 2
    assert params.tags == {'team': 'platform'}
    assert params.comparable_from_version == 1
