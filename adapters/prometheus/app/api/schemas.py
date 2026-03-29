"""Pydantic models for the adapter's REST API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

ALLOWED_METHODS = frozenset(
    ["min", "mean", "max", "std", "sum", "median", "p75", "p90", "p95", "p99"]
)


class RawQuerySpec(BaseModel):
    """Single instant-query spec that returns one scalar value."""

    mode: str = "raw"
    query: str


class AggregatedQuerySpec(BaseModel):
    """Range-query spec that aggregates results over the evaluation window."""

    mode: str = "aggregated"
    query_template: str
    interval: str
    methods: list[str] = Field(min_length=1)

    @field_validator("methods")
    @classmethod
    def validate_methods(cls, v: list[str]) -> list[str]:
        """Reject any method name not in the supported aggregation set."""
        invalid = set(v) - ALLOWED_METHODS
        if invalid:
            msg = f"invalid aggregation methods: {', '.join(sorted(invalid))}"
            raise ValueError(msg)
        return v


class JobSubmitRequest(BaseModel):
    """Payload for POST /api/v1/query-jobs."""

    queries: dict[str, dict[str, Any]] = Field(max_length=400)
    variables: dict[str, str] = {}
    start: datetime
    end: datetime
    timeout_seconds: int | None = None


class JobSubmitResponse(BaseModel):
    """Response body returned after a job is accepted (202)."""

    job_id: str
    status: str = "queued"
    created_at: datetime
    poll_url: str
    total_queries: int


class JobProgress(BaseModel):
    """Counts of total, completed, and failed queries within a job."""

    total: int
    completed: int
    failed: int


class JobStatusResponse(BaseModel):
    """Response body returned by GET /api/v1/query-jobs/{job_id}."""

    job_id: str
    status: str
    progress: JobProgress | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    results: list[dict[str, Any]] | None = None
    metadata: dict[str, Any] | None = None


class IndicatorResult(BaseModel):
    """Per-indicator query result returned inside a completed job."""

    indicator: str
    value: float | None
    success: bool
    message: str = ""
    query_executed: str = ""
