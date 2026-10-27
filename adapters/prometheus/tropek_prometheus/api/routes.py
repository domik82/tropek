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
            headers={'Retry-After': str(RETRY_AFTER_SECONDS)},
            media_type='application/json',
        )
    return result


@router.get('/query-jobs/{job_id}')
async def get_job(job_id: str, request: Request) -> dict[str, Any]:
    """Return the current status and results for a job."""
    manager: JobManager = request.app.state.job_manager
    job_status = await manager.get_status(job_id)
    if job_status is None:
        raise HTTPException(status_code=404, detail='job not found')
    return job_status


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
RETRY_AFTER_SECONDS = 5
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
        f'sync /query: {len(body.queries)} queries, datasource={x_datasource_name}, start={body.start}, end={body.end}'
    )
    manager: JobManager = request.app.state.job_manager
    try:
        result = await manager.submit(
            queries=body.queries,
            variables=body.variables,
            timeout_seconds=body.timeout_seconds,
            start=body.start,
            end=body.end,
        )
    except JobManager.QueueFullError:
        return JSONResponse(status_code=503, content={'detail': 'queue full'}, headers=_retry_headers())
    job_id = result['job_id']
    logger.info(f'sync /query: submitted job_id={job_id}, polling for completion')

    waited = await _wait_for_job(manager, job_id, result['timeout_seconds'] + BUDGET_GRACE_SECONDS)
    if isinstance(waited, JSONResponse):
        return waited

    response = _to_query_response(waited)
    logger.info(f'sync /query: job_id={job_id} done, values={len(response["values"])} errors={len(response["errors"])}')
    return response


def _retry_headers() -> dict[str, str]:
    return {'Retry-After': str(RETRY_AFTER_SECONDS)}


async def _wait_for_job(manager: JobManager, job_id: str, budget_seconds: int) -> dict[str, Any] | JSONResponse:
    """Poll a job until it finishes, is cancelled, or the budget runs out.

    :param JobManager manager: Manager that owns the job
    :param str job_id: Job to wait for
    :param int budget_seconds: Seconds to wait before cancelling the job
    :returns: The finished job's status, or a 503 (cancelled) / 504 (budget exhausted) response
    :rtype: dict[str, Any] | JSONResponse
    """
    deadline = time.monotonic() + budget_seconds
    while True:
        job_status = await manager.get_status(job_id)
        state = job_status.get('status') if job_status else None
        if job_status is not None and state in ('completed', 'timed_out'):
            return job_status
        if state == 'cancelled':
            # Cancelled under the caller (DELETE /api/v1/query-jobs/{id}); its results are incomplete,
            # so answer at once with a retryable status rather than waiting out the budget.
            logger.warning(f'sync /query: job_id={job_id} was cancelled while the caller waited')
            return JSONResponse(
                status_code=503,
                content={'detail': 'job was cancelled', 'job_id': job_id},
                headers=_retry_headers(),
            )
        if time.monotonic() > deadline:
            await manager.cancel(job_id)
            logger.error(f'sync query budget exhausted: job_id={job_id} budget_s={budget_seconds}')
            return JSONResponse(
                status_code=504,
                content={'detail': 'job did not complete within budget', 'job_id': job_id},
                headers=_retry_headers(),
            )
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)


def _to_query_response(job_status: dict[str, Any]) -> dict[str, Any]:
    """Rebuild the worker-protocol response from a finished job's status."""
    values: dict[str, float | None] = {}
    errors: dict[str, str] = {}
    error_kinds: dict[str, str] = {}
    for indicator in job_status.get('results', []):
        name = indicator['indicator']
        if indicator.get('success'):
            values[name] = indicator.get('value')
        else:
            values[name] = None
            errors[name] = indicator.get('message', 'unknown error')
            error_kinds[name] = indicator['kind']
    return {'values': values, 'errors': errors, 'metadata': job_status.get('metadata', {}), 'error_kinds': error_kinds}
