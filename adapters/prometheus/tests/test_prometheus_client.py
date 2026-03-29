import pytest
import respx
from httpx import Response

from app.core.prometheus_client import PrometheusClient, PrometheusQueryError


@pytest.fixture
def client():
    return PrometheusClient(base_url="http://prom:9090", timeout=5.0)


@respx.mock
@pytest.mark.asyncio
async def test_instant_query_returns_scalar(client: PrometheusClient):
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
    value = await client.instant_query("some_query", time="2026-01-15T10:00:00Z")
    assert value == 0.245


@respx.mock
@pytest.mark.asyncio
async def test_instant_query_zero_results_raises(client: PrometheusClient):
    respx.get("http://prom:9090/api/v1/query").mock(
        return_value=Response(
            200,
            json={
                "status": "success",
                "data": {"resultType": "vector", "result": []},
            },
        )
    )
    with pytest.raises(PrometheusQueryError, match="0 results"):
        await client.instant_query("some_query", time="2026-01-15T10:00:00Z")


@respx.mock
@pytest.mark.asyncio
async def test_instant_query_multiple_results_raises(client: PrometheusClient):
    respx.get("http://prom:9090/api/v1/query").mock(
        return_value=Response(
            200,
            json={
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": [
                        {"metric": {"a": "1"}, "value": [1705312800, "1.0"]},
                        {"metric": {"a": "2"}, "value": [1705312800, "2.0"]},
                    ],
                },
            },
        )
    )
    with pytest.raises(PrometheusQueryError, match="2 results"):
        await client.instant_query("some_query", time="2026-01-15T10:00:00Z")


@respx.mock
@pytest.mark.asyncio
async def test_instant_query_nan_raises(client: PrometheusClient):
    respx.get("http://prom:9090/api/v1/query").mock(
        return_value=Response(
            200,
            json={
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": [{"metric": {}, "value": [1705312800, "NaN"]}],
                },
            },
        )
    )
    with pytest.raises(PrometheusQueryError, match="NaN"):
        await client.instant_query("some_query", time="2026-01-15T10:00:00Z")


@respx.mock
@pytest.mark.asyncio
async def test_instant_query_scalar_result_type(client: PrometheusClient):
    respx.get("http://prom:9090/api/v1/query").mock(
        return_value=Response(
            200,
            json={
                "status": "success",
                "data": {"resultType": "scalar", "result": [1705312800, "42.5"]},
            },
        )
    )
    value = await client.instant_query("some_query", time="2026-01-15T10:00:00Z")
    assert value == 42.5


@respx.mock
@pytest.mark.asyncio
async def test_instant_query_http_error(client: PrometheusClient):
    respx.get("http://prom:9090/api/v1/query").mock(
        return_value=Response(500, text="Internal Server Error")
    )
    with pytest.raises(PrometheusQueryError, match="500"):
        await client.instant_query("some_query", time="2026-01-15T10:00:00Z")
