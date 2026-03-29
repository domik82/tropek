"""Tests for RawQueryStrategy."""

from urllib.parse import unquote

import pytest
import respx
from httpx import Response

from app.core.prometheus_client import PrometheusClient
from app.core.strategies.raw import RawQueryStrategy


@pytest.fixture
def strategy() -> RawQueryStrategy:
    client = PrometheusClient(base_url="http://prom:9090", timeout=5.0)
    return RawQueryStrategy(client)


@respx.mock
@pytest.mark.asyncio
async def test_raw_strategy_returns_single_value(strategy: RawQueryStrategy) -> None:
    respx.get("http://prom:9090/api/v1/query").mock(
        return_value=Response(
            200,
            json={
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": [{"metric": {}, "value": [1705312800, "0.245"]}],
                },
            },
        )
    )
    values, errors, metadata = await strategy.execute(
        sli_name="response_time_p99",
        query_spec={"mode": "raw", "query": "histogram_quantile(0.99, ...)"},
        variables={},
        start="2026-01-15T10:00:00Z",
        end="2026-01-15T10:05:00Z",
    )
    assert values == {"response_time_p99": 0.245}
    assert errors == {}
    assert metadata is None


@respx.mock
@pytest.mark.asyncio
async def test_raw_strategy_substitutes_variables(strategy: RawQueryStrategy) -> None:
    route = respx.get("http://prom:9090/api/v1/query").mock(
        return_value=Response(
            200,
            json={
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": [{"metric": {}, "value": [1705312800, "1.0"]}],
                },
            },
        )
    )
    await strategy.execute(
        sli_name="cpu",
        query_spec={"mode": "raw", "query": 'rate(cpu{job="$SERVICE"}[5m])'},
        variables={"SERVICE": "api"},
        start="2026-01-15T10:00:00Z",
        end="2026-01-15T10:05:00Z",
    )
    assert 'job="api"' in unquote(str(route.calls[0].request.url))


@respx.mock
@pytest.mark.asyncio
async def test_raw_strategy_captures_error(strategy: RawQueryStrategy) -> None:
    respx.get("http://prom:9090/api/v1/query").mock(
        return_value=Response(
            200,
            json={
                "status": "success",
                "data": {"resultType": "vector", "result": []},
            },
        )
    )
    values, errors, metadata = await strategy.execute(
        sli_name="missing_metric",
        query_spec={"mode": "raw", "query": "nonexistent_metric"},
        variables={},
        start="2026-01-15T10:00:00Z",
        end="2026-01-15T10:05:00Z",
    )
    assert values == {"missing_metric": None}
    assert "0 results" in errors["missing_metric"]
