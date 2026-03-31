"""Job submission, polling, cancellation, and synchronous query endpoints."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, Response
from pydantic import BaseModel

from app.api.schemas import JobSubmitRequest
from app.config import Settings
from app.core.job_manager import JobManager

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
# Submits a job internally, polls until complete, returns {values, errors}.
# ---------------------------------------------------------------------------


class SyncQueryRequest(BaseModel):
    """Request body for the synchronous POST /query endpoint."""

    queries: dict[str, dict[str, Any]]
    variables: dict[str, str] = {}
    start: str
    end: str


@sync_router.post('/query')
async def sync_query(
    body: SyncQueryRequest,
    request: Request,
    x_datasource_name: str = Header(default='default'),
) -> dict[str, Any]:
    """Submit queries, wait for results, return {values, errors}."""
    logger.info(
        'sync /query: %d queries, datasource=%s, start=%s, end=%s',
        len(body.queries),
        x_datasource_name,
        body.start,
        body.end,
    )
    manager: JobManager = request.app.state.job_manager
    result = await manager.submit(
        queries=body.queries,
        variables=body.variables,
        timeout_seconds=None,
        start=body.start,
        end=body.end,
    )
    job_id = result['job_id']
    logger.info('sync /query: submitted job_id=%s, polling for completion', job_id)

    # Poll until job finishes.  The coordinator's per-query timeout is
    # QUERY_TIMEOUT_SECONDS (default 30s).  We allow 2x that so the job
    # always finishes before this loop gives up.
    settings: Settings = Settings()
    max_polls = int(settings.query_timeout_seconds * 2 / 0.1)
    for _ in range(max_polls):
        status = await manager.get_status(job_id)
        if status and status.get('status') in ('completed', 'timed_out'):
            break
        await asyncio.sleep(0.1)
    else:
        logger.error('sync /query: job_id=%s did not complete in time', job_id)
        raise HTTPException(status_code=504, detail='job did not complete in time')

    values: dict[str, float | None] = {}
    errors: dict[str, str] = {}
    for indicator in status.get('results', []):
        name = indicator['indicator']
        if indicator.get('success'):
            values[name] = indicator.get('value')
        else:
            values[name] = None
            errors[name] = indicator.get('message', 'unknown error')

    logger.info(
        'sync /query: job_id=%s done, values=%d errors=%d',
        job_id,
        len(values),
        len(errors),
    )
    metadata = status.get('metadata', {})
    return {'values': values, 'errors': errors, 'metadata': metadata}
