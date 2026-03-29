"""Job lifecycle management — submit, poll, cancel."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.config import Settings
from app.redis.repository import JobRepository


class JobManager:
    """Coordinates job creation, status queries, and cancellation."""

    class QueueFullError(Exception):
        """Raised when the pending queue exceeds max depth."""

    def __init__(self, repo: JobRepository, settings: Settings) -> None:
        self._repo = repo
        self._settings = settings

    async def submit(
        self,
        queries: dict[str, dict[str, Any]],
        variables: dict[str, str],
        timeout_seconds: int | None,
        start: str = '',
        end: str = '',
    ) -> dict[str, Any]:
        """Create and enqueue a new job, enforcing queue depth and timeout limits."""
        depth = await self._repo.queue_depth()
        if depth >= self._settings.max_queue_depth:
            raise self.QueueFullError(f'queue depth {depth} >= max {self._settings.max_queue_depth}')

        timeout = min(
            timeout_seconds or self._settings.default_job_timeout_seconds,
            self._settings.max_job_timeout_seconds,
        )

        job_id = await self._repo.create_job(queries, variables, timeout, start, end)
        await self._repo.enqueue(job_id)

        return {
            'job_id': job_id,
            'status': 'queued',
            'created_at': datetime.now(UTC),
            'poll_url': f'/api/v1/query-jobs/{job_id}',
            'total_queries': len(queries),
        }

    async def get_status(self, job_id: str) -> dict[str, Any] | None:
        """Return current job status, or None if not found."""
        status = await self._repo.get_status(job_id)
        if status is None:
            return None

        result: dict[str, Any] = {
            'job_id': job_id,
            'status': status['status'],
        }

        if status['status'] == 'running':
            result['progress'] = {
                'total': status['total_queries'],
                'completed': status['completed_count'],
                'failed': status['failed_count'],
            }
        elif status['status'] in ('completed', 'timed_out'):
            result['completed_at'] = status.get('completed_at')
            result['duration_ms'] = status.get('duration_ms')
            results = await self._repo.get_results(job_id)
            result['results'] = [{'indicator': k, **v} for k, v in results.items()]

        return result

    async def cancel(self, job_id: str) -> bool:
        """Cancel a job. Returns True if cancelled, False if already terminal."""
        return await self._repo.cancel(job_id)
