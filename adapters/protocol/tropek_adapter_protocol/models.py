"""TROPEK adapter protocol — shared request/response models.

Any TROPEK-compatible adapter must expose:
  POST /query   — accepts AdapterQueryRequest, returns AdapterQueryResponse
  GET  /health  — returns AdapterHealthResponse

These Pydantic models are the canonical definition of the adapter HTTP contract.
Adapter authors in any language should follow this shape. Python adapters can
import and use these models directly as FastAPI request/response types.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AdapterQueryRequest(BaseModel):
    """POST /query request body.

    Sent by the TROPEK worker to query metric values from a data source adapter.

    Fields:
        queries: Mapping of metric_name to query spec. Each spec is a dict with:
            - Raw mode:        {"mode": "raw", "query": "<promql or equivalent>"}
            - Aggregated mode: {"mode": "aggregated", "query_template": "...",
                                "interval": "1m", "methods": ["mean", "p95"]}
        variables: Key-value pairs for template substitution in queries.
            Always includes TROPEK_ASSET, TROPEK_EVALUATION, and time range vars.
        start: ISO 8601 timestamp — evaluation period start (inclusive).
        end: ISO 8601 timestamp — evaluation period end (inclusive).
    """

    queries: dict[str, dict[str, Any]] = Field(
        description='metric_name -> query spec mapping',
    )
    variables: dict[str, str] = Field(
        default_factory=dict,
        description='template variable substitutions',
    )
    start: datetime = Field(description='evaluation period start (ISO 8601)')
    end: datetime = Field(description='evaluation period end (ISO 8601)')


class AdapterQueryResponse(BaseModel):
    """POST /query response body.

    Fields:
        values: metric_name -> scalar value (float) or None if the metric
            could not be resolved. Every metric from the request should appear
            in either values or errors (or both, with values[name]=None).
        errors: metric_name -> human-readable error string for metrics that
            failed to resolve. The TROPEK engine treats errored metrics as None.
        metadata: Optional per-metric metadata dict. Used for observability
            (e.g. sample counts, chunk stats). Not used in scoring.
    """

    values: dict[str, float | None] = Field(default_factory=dict)
    errors: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, dict[str, Any]] = Field(default_factory=dict)


class AdapterHealthResponse(BaseModel):
    """GET /health response body.

    Fields:
        status: "ok" if the adapter and its backing data source are reachable.
        datasource: Human-readable name of the data source type (e.g. "prometheus").
    """

    status: str = 'ok'
    datasource: str = ''
