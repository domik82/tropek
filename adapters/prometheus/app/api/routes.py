"""Job submission, polling, and cancellation endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response

from app.api.schemas import JobSubmitRequest
from app.core.job_manager import JobManager

router = APIRouter(prefix="/api/v1", tags=["jobs"])


@router.post("/query-jobs", status_code=202, response_model=None)
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
            headers={"Retry-After": "5"},
            media_type="application/json",
        )
    return result


@router.get("/query-jobs/{job_id}")
async def get_job(job_id: str, request: Request) -> dict[str, Any]:
    """Return the current status and results for a job."""
    manager: JobManager = request.app.state.job_manager
    status = await manager.get_status(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="job not found")
    return status


@router.delete("/query-jobs/{job_id}", status_code=204)
async def cancel_job(job_id: str, request: Request) -> Response:
    """Cancel a pending or running job."""
    manager: JobManager = request.app.state.job_manager
    cancelled = await manager.cancel(job_id)
    if not cancelled:
        raise HTTPException(status_code=409, detail="job already in terminal state")
    return Response(status_code=204)
