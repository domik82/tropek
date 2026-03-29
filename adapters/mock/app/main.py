"""TROPEK Mock adapter — serves CSV-backed time-series data."""

from __future__ import annotations

import os
import random
from datetime import datetime
from pathlib import Path
from typing import Any

from app.csv_store import CsvStore
from fastapi import FastAPI, Header
from pydantic import BaseModel

app = FastAPI(title='TROPEK Mock Adapter', version='0.1.0')

DATA_DIR = Path(os.getenv('MOCK_DATA_DIR', '/app/data'))
_store = CsvStore(DATA_DIR)

_INTERVAL_UNITS = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}

_METHOD_MULTIPLIERS = {
    'min': 0.3,
    'mean': 1.0,
    'median': 0.95,
    'max': 2.5,
    'sum': 50.0,
    'std': 0.3,
    'p75': 1.3,
    'p90': 1.7,
    'p95': 2.0,
    'p99': 2.3,
}


class QueryRequest(BaseModel):
    """Adapter query request body."""

    queries: dict[str, str | dict]
    variables: dict[str, str] = {}
    start: datetime
    end: datetime


class QueryResponse(BaseModel):
    """Adapter query response body."""

    values: dict[str, float | None]
    errors: dict[str, str]
    metadata: dict[str, Any] = {}


@app.post('/query', response_model=QueryResponse)
async def query_metrics(
    body: QueryRequest,
    x_datasource_name: str = Header(default='default'),
) -> QueryResponse:
    """Execute metric queries against CSV data store."""
    values: dict[str, float | None] = {}
    errors: dict[str, str] = {}
    metadata: dict[str, Any] = {}

    for name, spec in body.queries.items():
        if isinstance(spec, dict) and spec.get('mode') == 'aggregated':
            _handle_aggregated(name, spec, body, values, metadata)
        else:
            query = spec['query'] if isinstance(spec, dict) else spec
            result = _store.query(
                namespace=x_datasource_name,
                queries={name: query},
                start=body.start,
                end=body.end,
            )
            values.update(result.values)
            errors.update(result.errors)

    return QueryResponse(values=values, errors=errors, metadata=metadata)


def _handle_aggregated(
    name: str,
    spec: dict,
    body: QueryRequest,
    values: dict[str, float | None],
    metadata: dict[str, Any],
) -> None:
    """Generate mock aggregated-mode results with realistic metadata."""
    methods = spec.get('methods', ['mean'])
    interval_seconds = _parse_interval(spec.get('interval', '1m'))
    window = (body.end - body.start).total_seconds()
    expected = max(1, int(window / interval_seconds))
    actual = max(1, int(expected * random.uniform(0.85, 1.0)))

    base = random.uniform(1.0, 100.0)
    for method in methods:
        key = f'{name}.{method}'
        multiplier = _METHOD_MULTIPLIERS.get(method, 1.0)
        values[key] = round(base * multiplier, 3)

    metadata[name] = {
        'mode': 'aggregated',
        'expected_samples': expected,
        'actual_samples': actual,
        'missing_pct': round((1 - actual / expected) * 100, 1) if expected else 0.0,
        'chunks_failed': 0,
    }


def _parse_interval(interval: str) -> int:
    """Parse Prometheus duration to seconds (e.g. '1m' -> 60)."""
    return int(interval[:-1]) * _INTERVAL_UNITS.get(interval[-1], 60)


@app.get('/health')
async def health() -> dict[str, str]:
    """Return adapter health status."""
    return {'status': 'ok', 'datasource': 'mock'}
