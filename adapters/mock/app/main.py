"""TROPEK Mock adapter — serves CSV-backed time-series data."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from app.csv_store import CsvStore
from fastapi import FastAPI, Header
from pydantic import BaseModel

app = FastAPI(title="TROPEK Mock Adapter", version="0.1.0")

DATA_DIR = Path(os.getenv("MOCK_DATA_DIR", "/app/data"))
_store = CsvStore(DATA_DIR)


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
    x_datasource_name: str = Header(default="default"),
) -> QueryResponse:
    """Execute metric queries against CSV data store."""
    result = _store.query(
        namespace=x_datasource_name,
        queries=body.queries,
        start=body.start,
        end=body.end,
    )
    return QueryResponse(values=result.values, errors=result.errors)


@app.get("/health")
async def health() -> dict[str, str]:
    """Return adapter health status."""
    return {"status": "ok", "datasource": "mock"}
