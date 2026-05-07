"""TROPEK Mock adapter — serves CSV-backed time-series data."""

from __future__ import annotations

import logging
import os
import random
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header
from pydantic import BaseModel
from tropek_mock.csv_store import CsvStore

LOG_FORMAT = '%(asctime)s [%(levelname)-7s] %(name)s: %(message)s'
LOG_DATEFMT = '%Y-%m-%d %H:%M:%S'

logger = logging.getLogger('mock-adapter')


def _configure_logging() -> None:
    """Set up logging to stderr and optionally to file via LOG_DIR."""
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATEFMT))
    root.addHandler(stderr_handler)

    log_dir = os.environ.get('LOG_DIR')
    if log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_path / 'mock-adapter.log',
            maxBytes=10 * 1024 * 1024,
            backupCount=100,
        )
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATEFMT))
        root.addHandler(file_handler)
        logger.info('file logging enabled: %s/mock-adapter.log', log_path)


_configure_logging()

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

    logger.info(
        'query request: namespace=%s start=%s end=%s queries=%s',
        x_datasource_name,
        body.start,
        body.end,
        list(body.queries.keys()),
    )

    for name, spec in body.queries.items():
        if isinstance(spec, dict) and spec.get('mode') == 'aggregated':
            _handle_aggregated(
                name,
                spec,
                body,
                x_datasource_name,
                values,
                errors,
                metadata,
            )
        else:
            query = spec['query'] if isinstance(spec, dict) else spec
            result = _store.query(
                namespace=x_datasource_name,
                queries={name: query},
                variables=body.variables,
                start=body.start,
                end=body.end,
            )
            for k, v in result.values.items():
                logger.info('  raw metric: %s = %s', k, v)
            for k, v in result.errors.items():
                logger.warning('  raw metric error: %s = %s', k, v)
            values.update(result.values)
            errors.update(result.errors)

    logger.info(
        'query response: values=%s errors=%s',
        dict(values),
        dict(errors) if errors else '{}',
    )
    return QueryResponse(values=values, errors=errors, metadata=metadata)


def _handle_aggregated(
    name: str,
    spec: dict,
    body: QueryRequest,
    namespace: str,
    values: dict[str, float | None],
    errors: dict[str, str],
    metadata: dict[str, Any],
) -> None:
    """Generate mock aggregated-mode results using CSV data when available."""
    methods = spec.get('methods', ['mean'])
    interval_seconds = _parse_interval(spec.get('interval', '1m'))
    window = (body.end - body.start).total_seconds()
    expected = max(1, int(window / interval_seconds))

    # Check CSV store for the SLI metric — mirrors real adapter behaviour
    csv_result = _store.query(
        namespace=namespace,
        queries={name: name},
        variables=body.variables,
        start=body.start,
        end=body.end,
    )
    base_value = csv_result.values.get(name)

    logger.info(
        '  aggregated CSV lookup: sli=%s namespace=%s base_value=%s csv_errors=%s',
        name,
        namespace,
        base_value,
        csv_result.errors,
    )

    if base_value is None:
        # No data in CSV → report error for every method key
        for method in methods:
            key = f'{name}.{method}'
            values[key] = None
            errors[key] = f'no data for {name}'
        logger.warning('  aggregated: no CSV data for %s — returning errors for %s', name, methods)
        metadata[name] = {
            'mode': 'aggregated',
            'expected_samples': expected,
            'actual_samples': 0,
            'missing_pct': 100.0,
            'chunks_failed': 0,
        }
        return

    actual = max(1, int(expected * random.uniform(0.85, 1.0)))  # noqa: S311
    for method in methods:
        key = f'{name}.{method}'
        multiplier = _METHOD_MULTIPLIERS.get(method, 1.0)
        values[key] = round(base_value * multiplier, 3)

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
