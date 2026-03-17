"""TROPEK Prometheus adapter — queries Prometheus and returns scalar values."""

from __future__ import annotations

import os
from datetime import datetime

import httpx
from fastapi import FastAPI, Header
from pydantic import BaseModel

app = FastAPI(title="TROPEK Prometheus Adapter", version="0.2.0")

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
QUERY_TIMEOUT = int(os.getenv("QUERY_TIMEOUT_SECONDS", "30"))


class QueryRequest(BaseModel):
    """Adapter query request body."""

    queries: dict[str, str]
    start: datetime
    end: datetime


class QueryResponse(BaseModel):
    """Adapter query response body."""

    values: dict[str, float]
    errors: dict[str, str]


@app.post("/query", response_model=QueryResponse)
async def query_metrics(
    body: QueryRequest,
    x_datasource_name: str = Header(default=""),
) -> QueryResponse:
    """Execute PromQL queries against Prometheus and return scalar results."""
    values: dict[str, float] = {}
    errors: dict[str, str] = {}

    step = _calculate_step(body.start, body.end)

    async with httpx.AsyncClient(timeout=QUERY_TIMEOUT) as client:
        for metric_name, promql in body.queries.items():
            try:
                resp = await client.get(
                    f"{PROMETHEUS_URL}/api/v1/query_range",
                    params={
                        "query": promql,
                        "start": body.start.isoformat(),
                        "end": body.end.isoformat(),
                        "step": step,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

                if data.get("status") != "success":
                    errors[metric_name] = data.get("error", "prometheus query failed")
                    continue

                result = data.get("data", {}).get("result", [])
                if len(result) == 0:
                    errors[metric_name] = "no data returned for query"
                elif len(result) > 1:
                    errors[metric_name] = f"query returned {len(result)} series, expected 1"
                else:
                    # Single series — take the last data point
                    series_values = result[0].get("values", [])
                    if not series_values:
                        errors[metric_name] = "series has no data points"
                    else:
                        values[metric_name] = float(series_values[-1][1])

            except httpx.TimeoutException:
                errors[metric_name] = f"query timed out after {QUERY_TIMEOUT}s"
            except httpx.HTTPStatusError as exc:
                errors[metric_name] = f"prometheus returned {exc.response.status_code}"
            except httpx.ConnectError:
                errors[metric_name] = f"could not reach prometheus at {PROMETHEUS_URL}"

    return QueryResponse(values=values, errors=errors)


@app.get("/health")
async def health() -> dict[str, str]:
    """Return adapter health status and datasource identifier."""
    return {"status": "ok", "datasource": "prometheus"}


def _calculate_step(start: datetime, end: datetime) -> str:
    """Auto-calculate query step to keep result set manageable."""
    duration = (end - start).total_seconds()
    step_seconds = max(15, int(duration / 300))
    return f"{step_seconds}s"
