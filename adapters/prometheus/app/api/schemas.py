"""Pydantic models for the adapter's REST API."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

ALLOWED_METHODS = frozenset(
    ["min", "mean", "max", "std", "sum", "median", "p75", "p90", "p95", "p99"]
)


class RawQuerySpec(BaseModel):
    mode: str = "raw"
    query: str


class AggregatedQuerySpec(BaseModel):
    mode: str = "aggregated"
    query_template: str
    interval: str
    methods: list[str] = Field(min_length=1)

    @field_validator("methods")
    @classmethod
    def validate_methods(cls, v: list[str]) -> list[str]:
        invalid = set(v) - ALLOWED_METHODS
        if invalid:
            msg = f"invalid aggregation methods: {', '.join(sorted(invalid))}"
            raise ValueError(msg)
        return v


class JobSubmitRequest(BaseModel):
    queries: dict[str, dict] = Field(max_length=400)
    variables: dict[str, str] = {}
    start: datetime
    end: datetime
    timeout_seconds: int | None = None


class JobSubmitResponse(BaseModel):
    job_id: str
    status: str = "queued"
    created_at: datetime
    poll_url: str
    total_queries: int


class JobProgress(BaseModel):
    total: int
    completed: int
    failed: int


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: JobProgress | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    results: list[dict] | None = None
    metadata: dict | None = None


class IndicatorResult(BaseModel):
    indicator: str
    value: float | None
    success: bool
    message: str = ""
    query_executed: str = ""
