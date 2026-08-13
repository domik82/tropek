"""Tests for SLI definition mode-dependent validation."""

import pytest
from pydantic import ValidationError
from tropek.modules.sli_registry.schemas import AggregationMethod, SLIDefinitionCreate


class TestRawModeValidation:
    def test_raw_mode_with_indicators_valid(self) -> None:
        sli = SLIDefinitionCreate(
            name='test',
            adapter_type='prometheus',
            mode='raw',
            indicators={'cpu': 'rate(cpu[5m])'},
        )
        assert sli.mode == 'raw'
        assert sli.indicators == {'cpu': 'rate(cpu[5m])'}

    def test_raw_mode_without_indicators_rejected(self) -> None:
        with pytest.raises(ValidationError, match='indicators'):
            SLIDefinitionCreate(
                name='test',
                adapter_type='prometheus',
                mode='raw',
                indicators={},
            )

    def test_raw_mode_with_aggregated_fields_rejected(self) -> None:
        with pytest.raises(ValidationError, match='query_template'):
            SLIDefinitionCreate(
                name='test',
                adapter_type='prometheus',
                mode='raw',
                indicators={'cpu': 'rate(cpu[5m])'},
                query_template='rate(cpu[$interval])',
            )

    def test_raw_mode_default(self) -> None:
        sli = SLIDefinitionCreate(
            name='test',
            adapter_type='prometheus',
            indicators={'cpu': 'rate(cpu[5m])'},
        )
        assert sli.mode == 'raw'


class TestAggregatedModeValidation:
    def test_aggregated_mode_valid(self) -> None:
        sli = SLIDefinitionCreate(
            name='test',
            adapter_type='prometheus',
            mode='aggregated',
            query_template='rate(cpu[$interval])',
            interval='1m',
            methods=[AggregationMethod.MEAN, AggregationMethod.P99],
        )
        assert sli.mode == 'aggregated'

    def test_aggregated_mode_accepts_string_methods(self) -> None:
        """Pydantic coerces plain strings to AggregationMethod enum values."""
        sli = SLIDefinitionCreate(
            name='test',
            adapter_type='prometheus',
            mode='aggregated',
            query_template='rate(cpu[$interval])',
            interval='1m',
            methods=['mean', 'p99'],
        )
        assert sli.methods == [AggregationMethod.MEAN, AggregationMethod.P99]

    def test_aggregated_mode_without_query_template_rejected(self) -> None:
        with pytest.raises(ValidationError, match='query_template'):
            SLIDefinitionCreate(
                name='test',
                adapter_type='prometheus',
                mode='aggregated',
                interval='1m',
                methods=['mean'],
            )

    def test_aggregated_mode_without_interval_rejected(self) -> None:
        with pytest.raises(ValidationError, match='interval'):
            SLIDefinitionCreate(
                name='test',
                adapter_type='prometheus',
                mode='aggregated',
                query_template='rate(cpu[$interval])',
                methods=['mean'],
            )

    def test_aggregated_mode_without_methods_rejected(self) -> None:
        with pytest.raises(ValidationError, match='methods'):
            SLIDefinitionCreate(
                name='test',
                adapter_type='prometheus',
                mode='aggregated',
                query_template='rate(cpu[$interval])',
                interval='1m',
            )

    def test_aggregated_mode_empty_methods_rejected(self) -> None:
        with pytest.raises(ValidationError, match='methods'):
            SLIDefinitionCreate(
                name='test',
                adapter_type='prometheus',
                mode='aggregated',
                query_template='rate(cpu[$interval])',
                interval='1m',
                methods=[],
            )

    def test_aggregated_mode_invalid_method_rejected(self) -> None:
        with pytest.raises(ValidationError, match='invalid_method'):
            SLIDefinitionCreate(
                name='test',
                adapter_type='prometheus',
                mode='aggregated',
                query_template='rate(cpu[$interval])',
                interval='1m',
                methods=['mean', 'invalid_method'],
            )

    def test_aggregated_mode_all_methods_valid(self) -> None:
        sli = SLIDefinitionCreate(
            name='test',
            adapter_type='prometheus',
            mode='aggregated',
            query_template='rate(cpu[$interval])',
            interval='1m',
            methods=list(AggregationMethod),
        )
        assert set(sli.methods) == set(AggregationMethod)

    def test_invalid_mode_rejected(self) -> None:
        with pytest.raises(ValidationError, match='mode'):
            SLIDefinitionCreate(
                name='test',
                adapter_type='prometheus',
                mode='unknown',
                indicators={'cpu': 'rate(cpu[5m])'},
            )

    def test_enum_has_ten_members(self) -> None:
        assert len(AggregationMethod) == 10


class TestAggregatedMultiIndicator:
    def test_aggregated_mode_with_indicators_valid(self) -> None:
        sli = SLIDefinitionCreate(
            name='test',
            adapter_type='prometheus',
            mode='aggregated',
            interval='5m',
            methods=[AggregationMethod.MEAN, AggregationMethod.MAX],
            indicators={'cpu': 'rate(cpu[$interval])', 'mem': 'mem_bytes'},
        )
        assert sli.indicators == {'cpu': 'rate(cpu[$interval])', 'mem': 'mem_bytes'}
        assert sli.query_template is None

    def test_aggregated_mode_with_both_indicators_and_template_rejected(self) -> None:
        with pytest.raises(ValidationError, match='not both'):
            SLIDefinitionCreate(
                name='test',
                adapter_type='prometheus',
                mode='aggregated',
                interval='5m',
                methods=[AggregationMethod.MEAN],
                indicators={'cpu': 'rate(cpu[$interval])'},
                query_template='rate(cpu[$interval])',
            )

    def test_aggregated_mode_with_neither_rejected(self) -> None:
        with pytest.raises(ValidationError, match='indicators or query_template'):
            SLIDefinitionCreate(
                name='test',
                adapter_type='prometheus',
                mode='aggregated',
                interval='5m',
                methods=[AggregationMethod.MEAN],
            )

    def test_aggregated_mode_indicators_still_require_methods(self) -> None:
        with pytest.raises(ValidationError, match='methods'):
            SLIDefinitionCreate(
                name='test',
                adapter_type='prometheus',
                mode='aggregated',
                interval='5m',
                indicators={'cpu': 'rate(cpu[$interval])'},
            )

    def test_aggregated_mode_single_template_still_valid(self) -> None:
        sli = SLIDefinitionCreate(
            name='test',
            adapter_type='prometheus',
            mode='aggregated',
            interval='1m',
            methods=[AggregationMethod.MEAN],
            query_template='http_request_duration_seconds',
        )
        assert sli.query_template == 'http_request_duration_seconds'
        assert sli.indicators == {}
