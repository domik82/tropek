import pytest
from app.api.schemas import AggregatedQuerySpec, JobSubmitRequest, RawQuerySpec
from pydantic import ValidationError


def test_raw_query_spec_valid():
    spec = RawQuerySpec(mode='raw', query='rate(http_requests[5m])')
    assert spec.mode == 'raw'
    assert spec.query == 'rate(http_requests[5m])'


def test_aggregated_query_spec_valid():
    spec = AggregatedQuerySpec(
        mode='aggregated',
        query_template='rate(cpu[$interval])',
        interval='1m',
        methods=['mean', 'p99'],
    )
    assert spec.mode == 'aggregated'
    assert spec.methods == ['mean', 'p99']


def test_aggregated_query_spec_invalid_method():
    with pytest.raises(ValidationError):
        AggregatedQuerySpec(
            mode='aggregated',
            query_template='rate(cpu[$interval])',
            interval='1m',
            methods=['mean', 'invalid_method'],
        )


def test_aggregated_query_spec_empty_methods():
    with pytest.raises(ValidationError):
        AggregatedQuerySpec(
            mode='aggregated',
            query_template='rate(cpu[$interval])',
            interval='1m',
            methods=[],
        )


def test_job_submit_request_valid():
    req = JobSubmitRequest(
        queries={
            'cpu': {'mode': 'raw', 'query': 'rate(cpu[5m])'},
        },
        start='2026-01-15T10:00:00Z',
        end='2026-01-15T10:05:00Z',
    )
    assert len(req.queries) == 1


def test_job_submit_request_too_many_queries():
    queries = {f'metric_{i}': {'mode': 'raw', 'query': 'x'} for i in range(401)}
    with pytest.raises(ValidationError, match='at most 400'):
        JobSubmitRequest(
            queries=queries,
            start='2026-01-15T10:00:00Z',
            end='2026-01-15T10:05:00Z',
        )
