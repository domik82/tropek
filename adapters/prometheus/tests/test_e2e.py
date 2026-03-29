"""End-to-end smoke tests for the Prometheus SLI adapter.

Requires:
  1. Observability stack: cd observability_stack/integration-test && just up
  2. Redis on localhost:6379 (or set REDIS_URL)
  3. Adapter running on localhost:8081 (or set ADAPTER_URL)

Run:
  uv run --directory adapters/prometheus pytest tests/test_e2e.py -v -m e2e
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx
import pytest

ADAPTER_URL = os.environ.get("ADAPTER_URL", "http://localhost:8081")
QUERY_START = os.environ.get("QUERY_START", "2026-03-18T12:00:00Z")
QUERY_END = os.environ.get("QUERY_END", "2026-03-18T12:05:00Z")

pytestmark = pytest.mark.e2e


async def poll_job(
    client: httpx.AsyncClient,
    job_id: str,
    *,
    max_attempts: int = 30,
    interval: float = 0.2,
) -> dict[str, Any]:
    """Poll a job until it reaches a terminal state."""
    for _ in range(max_attempts):
        resp = await client.get(f"{ADAPTER_URL}/api/v1/query-jobs/{job_id}")
        resp.raise_for_status()
        data = resp.json()
        if data["status"] in ("completed", "timed_out"):
            return data
        await asyncio.sleep(interval)
    return data


@pytest.fixture
async def client():
    """Async httpx client scoped to each test."""
    async with httpx.AsyncClient(timeout=30.0) as c:
        yield c


class TestHealth:
    """Health endpoint checks."""

    async def test_liveness(self, client: httpx.AsyncClient) -> None:
        resp = await client.get(f"{ADAPTER_URL}/health/live")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    async def test_readiness(self, client: httpx.AsyncClient) -> None:
        resp = await client.get(f"{ADAPTER_URL}/health/ready")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestSingleQuery:
    """Submit and poll a single raw query."""

    async def test_submit_returns_202(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            f"{ADAPTER_URL}/api/v1/query-jobs",
            json={
                "queries": {
                    "cpu": {
                        "mode": "raw",
                        "query": 'avg(cpu_usage_percent{service="api"})',
                    },
                },
                "start": QUERY_START,
                "end": QUERY_END,
            },
        )
        assert resp.status_code == 202
        body = resp.json()
        assert body["status"] == "queued"
        assert "job_id" in body
        assert body["total_queries"] == 1

    async def test_job_completes_with_result(self, client: httpx.AsyncClient) -> None:
        submit = await client.post(
            f"{ADAPTER_URL}/api/v1/query-jobs",
            json={
                "queries": {
                    "cpu": {
                        "mode": "raw",
                        "query": 'avg(cpu_usage_percent{service="api"})',
                    },
                },
                "start": QUERY_START,
                "end": QUERY_END,
            },
        )
        job_id = submit.json()["job_id"]
        result = await poll_job(client, job_id)
        assert result["status"] == "completed"
        assert len(result["results"]) == 1
        assert result["results"][0]["indicator"] == "cpu"


class TestMultiQuery:
    """Submit a multi-metric job."""

    async def test_three_metrics_return_three_results(
        self, client: httpx.AsyncClient
    ) -> None:
        submit = await client.post(
            f"{ADAPTER_URL}/api/v1/query-jobs",
            json={
                "queries": {
                    "error_rate": {
                        "mode": "raw",
                        "query": (
                            'sum(rate(http_errors_total{service="api"}[5m]))'
                            ' / sum(rate(http_requests_total{service="api"}[5m]))'
                        ),
                    },
                    "cpu": {
                        "mode": "raw",
                        "query": 'avg(cpu_usage_percent{service="api"})',
                    },
                    "p99_latency": {
                        "mode": "raw",
                        "query": (
                            "histogram_quantile(0.99,"
                            ' sum(rate(http_request_duration_seconds_bucket{service="api"}[5m]))'
                            " by (le))"
                        ),
                    },
                },
                "start": QUERY_START,
                "end": QUERY_END,
            },
        )
        job_id = submit.json()["job_id"]
        result = await poll_job(client, job_id)
        assert result["status"] == "completed"
        assert len(result["results"]) == 3
        indicators = {r["indicator"] for r in result["results"]}
        assert indicators == {"error_rate", "cpu", "p99_latency"}


class TestVariableSubstitution:
    """Variable substitution in queries."""

    async def test_user_variable_resolved(self, client: httpx.AsyncClient) -> None:
        submit = await client.post(
            f"{ADAPTER_URL}/api/v1/query-jobs",
            json={
                "queries": {
                    "cpu_by_service": {
                        "mode": "raw",
                        "query": 'avg(cpu_usage_percent{service="$SERVICE"})',
                    },
                },
                "variables": {"SERVICE": "frontend"},
                "start": QUERY_START,
                "end": QUERY_END,
            },
        )
        job_id = submit.json()["job_id"]
        result = await poll_job(client, job_id)
        assert result["status"] == "completed"

    async def test_duration_seconds_auto_computed(
        self, client: httpx.AsyncClient
    ) -> None:
        submit = await client.post(
            f"{ADAPTER_URL}/api/v1/query-jobs",
            json={
                "queries": {
                    "with_duration": {
                        "mode": "raw",
                        "query": (
                            'avg_over_time(cpu_usage_percent{service="api"}'
                            "[$DURATION_SECONDS])"
                        ),
                    },
                },
                "start": QUERY_START,
                "end": QUERY_END,
            },
        )
        job_id = submit.json()["job_id"]
        result = await poll_job(client, job_id)
        assert result["status"] == "completed"


class TestErrorHandling:
    """Error scenarios."""

    async def test_nonexistent_metric_returns_error(
        self, client: httpx.AsyncClient
    ) -> None:
        submit = await client.post(
            f"{ADAPTER_URL}/api/v1/query-jobs",
            json={
                "queries": {
                    "missing": {
                        "mode": "raw",
                        "query": "definitely_not_a_real_metric_xyz",
                    },
                },
                "start": QUERY_START,
                "end": QUERY_END,
            },
        )
        job_id = submit.json()["job_id"]
        result = await poll_job(client, job_id)
        assert result["status"] == "completed"
        assert len(result["results"]) == 1
        assert result["results"][0]["success"] is False

    async def test_unknown_job_returns_404(self, client: httpx.AsyncClient) -> None:
        resp = await client.get(
            f"{ADAPTER_URL}/api/v1/query-jobs/00000000-0000-0000-0000-000000000000"
        )
        assert resp.status_code == 404


class TestCancel:
    """Job cancellation."""

    async def test_cancel_returns_204_or_409(self, client: httpx.AsyncClient) -> None:
        """Cancel may return 204 (cancelled) or 409 (already completed by coordinator)."""
        submit = await client.post(
            f"{ADAPTER_URL}/api/v1/query-jobs",
            json={
                "queries": {
                    "slow": {"mode": "raw", "query": "up"},
                },
                "start": QUERY_START,
                "end": QUERY_END,
            },
        )
        job_id = submit.json()["job_id"]
        resp = await client.delete(f"{ADAPTER_URL}/api/v1/query-jobs/{job_id}")
        assert resp.status_code in (204, 409)
