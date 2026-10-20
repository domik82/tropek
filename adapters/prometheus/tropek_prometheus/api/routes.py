"""Job submission, polling, cancellation, and synchronous query endpoints."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from tropek_prometheus.api.schemas import JobSubmitRequest
from tropek_prometheus.config import Settings
from tropek_prometheus.core.job_manager import JobManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/api/v1', tags=['jobs'])
sync_router = APIRouter(tags=['sync'])


@router.post('/query-jobs', status_code=202, response_model=None)
async def submit_job(body: JobSubmitRequest, request: Request) -> Response | dict[str, Any]:
    """Submit a batch of queries as a new job."""
    manager: JobManager = request.app.state.job_manager
    try:
        result = await manager.submit(
            queries=body.queries,
            variables=body.variables,
            timeout_seconds=body.timeout_seconds,
            start=body.start.isoformat(),
            end=body.end.isoformat(),
        )
    except JobManager.QueueFullError:
        return Response(
            content='{"error": "queue full"}',
            status_code=503,
            headers={'Retry-After': '5'},
            media_type='application/json',
        )
    return result


@router.get('/query-jobs/{job_id}')
async def get_job(job_id: str, request: Request) -> dict[str, Any]:
    """Return the current status and results for a job."""
    manager: JobManager = request.app.state.job_manager
    status = await manager.get_status(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail='job not found')
    return status


@router.delete('/query-jobs/{job_id}', status_code=204)
async def cancel_job(job_id: str, request: Request) -> Response:
    """Cancel a pending or running job."""
    manager: JobManager = request.app.state.job_manager
    cancelled = await manager.cancel(job_id)
    if not cancelled:
        raise HTTPException(status_code=409, detail='job already in terminal state')
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Synchronous /query — compatibility with the TROPEK worker adapter protocol.
# Submits a job internally, polls until complete, returns {values, errors, metadata, error_kinds}.
# ---------------------------------------------------------------------------

# Seconds a caller's budget exceeds the job timeout by, so the job's own timeout (which records
# per-query results) always fires before the endpoint gives up.
BUDGET_GRACE_SECONDS = 5
RETRY_AFTER_SECONDS = '5'
_POLL_INTERVAL_SECONDS = 0.1


class SyncQueryRequest(BaseModel):
    """Request body for the synchronous POST /query endpoint."""

    queries: dict[str, dict[str, Any]]
    variables: dict[str, str] = {}
    start: str
    end: str
    timeout_seconds: int | None = Field(default=None, ge=1)


@sync_router.post('/query', response_model=None)
async def sync_query(
    body: SyncQueryRequest,
    request: Request,
    x_datasource_name: str = Header(default='default'),
) -> Response | dict[str, Any]:
    """Submit queries, wait for results within the caller's budget, return the results.

    The job runs under ``timeout_seconds`` (capped at the configured maximum); the endpoint waits that
    long plus a grace period. Responds 503 when the queue is full or the job was cancelled while the caller
    waited, and 504 when the budget runs out, all with ``Retry-After``, so callers can tell "try again later"
    from a real failure.
    """
    logger.info(
        'sync /query: %d queries, datasource=%s, start=%s, end=%s',
        len(body.queries),
        x_datasource_name,
        body.start,
        body.end,
    )
    manager: JobManager = request.app.state.job_manager
    settings: Settings = request.app.state.settings
    retry_headers = {'Retry-After': RETRY_AFTER_SECONDS}
    try:
        result = await manager.submit(
            queries=body.queries,
            variables=body.variables,
            timeout_seconds=body.timeout_seconds,
            start=body.start,
            end=body.end,
        )
    except JobManager.QueueFullError:
        return JSONResponse(status_code=503, content={'detail': 'queue full'}, headers=retry_headers)
    job_id = result['job_id']
    logger.info('sync /query: submitted job_id=%s, polling for completion', job_id)

    job_timeout = min(body.timeout_seconds or settings.default_job_timeout_seconds, settings.max_job_timeout_seconds)
    budget_seconds = job_timeout + BUDGET_GRACE_SECONDS
    deadline = time.monotonic() + budget_seconds
    while True:
        status = await manager.get_status(job_id)
        job_state = status.get('status') if status else None
        if status is not None and job_state in ('completed', 'timed_out'):
            break
        if job_state == 'cancelled':
            # Cancelled under the caller (DELETE /api/v1/query-jobs/{id}); its results are incomplete,
            # so answer at once with a retryable status rather than waiting out the budget.
            logger.warning('sync /query: job_id=%s was cancelled while the caller waited', job_id)
            return JSONResponse(
                status_code=503,
                content={'detail': 'job was cancelled', 'job_id': job_id},
                headers=retry_headers,
            )
        if time.monotonic() > deadline:
            await manager.cancel(job_id)
            logger.error('sync query budget exhausted: job_id=%s budget_s=%d', job_id, budget_seconds)
            return JSONResponse(
                status_code=504,
                content={'detail': 'job did not complete within budget', 'job_id': job_id},
                headers=retry_headers,
            )
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)

    values: dict[str, float | None] = {}
    errors: dict[str, str] = {}
    error_kinds: dict[str, str] = {}
    for indicator in status.get('results', []):
        name = indicator['indicator']
        if indicator.get('success'):
            values[name] = indicator.get('value')
        else:
            values[name] = None
            errors[name] = indicator.get('message', 'unknown error')
            # Results written before `kind` existed carry none and read as permanent failures.
            error_kinds[name] = indicator.get('kind', 'data')

    logger.info(
        'sync /query: job_id=%s done, values=%d errors=%d',
        job_id,
        len(values),
        len(errors),
    )
    metadata = status.get('metadata', {})
    return {'values': values, 'errors': errors, 'metadata': metadata, 'error_kinds': error_kinds}
