"""Background coordinator: picks jobs from queue, fans out queries."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from tropek_prometheus.config import Settings
from tropek_prometheus.redis.repository import JobRepository

logger = logging.getLogger(__name__)


class Coordinator:
    """Dequeues jobs and processes them with semaphore-limited concurrency."""

    def __init__(
        self,
        repo: JobRepository,
        settings: Settings,
        strategies: dict[str, Any],
    ) -> None:
        self._repo = repo
        self._settings = settings
        self._strategies = strategies
        self._semaphore = asyncio.Semaphore(settings.max_concurrent_queries)
        self._job_semaphore = asyncio.Semaphore(settings.max_concurrent_jobs)
        self._running = False

    async def _run_query(
        self,
        *,
        job_id: str,
        sli_name: str,
        query_spec: dict[str, Any],
        variables: dict[str, str],
        start: str,
        end: str,
    ) -> None:
        """Execute one SLI's query and record its results.

        Failures are recorded against this SLI rather than raised, so that one malformed spec
        cannot abandon its sibling queries or leave the job stuck in ``running``.

        :param str job_id: Job the query belongs to.
        :param str sli_name: Name of the SLI being queried.
        :param dict[str, Any] query_spec: The SLI's query specification.
        :param dict[str, str] variables: Variables available for substitution.
        :param str start: Evaluation window start.
        :param str end: Evaluation window end.
        """
        query_executed = query_spec.get('query', query_spec.get('query_template', ''))
        mode = query_spec.get('mode', 'raw')
        strategy = self._strategies.get(mode)
        if strategy is None:
            await self._repo.write_result(
                job_id,
                sli_name,
                value=None,
                success=False,
                message=f'unsupported mode: {mode}',
            )
            return

        async with self._semaphore:
            # Check cancellation before executing
            current = await self._repo.get_status(job_id)
            if current and current['status'] == 'cancelled':
                return

            try:
                values, errors, metadata = await strategy.execute(
                    sli_name=sli_name,
                    query_spec=query_spec,
                    variables=variables,
                    start=start,
                    end=end,
                )
            except Exception as exc:
                # A malformed spec must cost its own SLI, not the whole job: an exception escaping
                # here would abandon every sibling query and leave the job running.
                logger.exception('query failed: job=%s sli=%s', job_id, sli_name)
                await self._repo.write_result(
                    job_id,
                    sli_name,
                    value=None,
                    success=False,
                    message=f'{type(exc).__name__}: {exc}',
                    query_executed=query_executed,
                )
                return

            for name, value in values.items():
                await self._repo.write_result(
                    job_id,
                    name,
                    value=value,
                    success=name not in errors,
                    message=errors.get(name, ''),
                    query_executed=query_executed,
                )

            if metadata is not None:
                await self._repo.write_metadata(job_id, sli_name, metadata)

    async def process_one(self) -> bool:
        """Process a single job from the queue. Returns True if a job was processed."""
        job_id = await self._repo.dequeue()
        if job_id is None:
            return False

        logger.info('dequeued job: id=%s', job_id)
        status = await self._repo.get_status(job_id)
        if status is None or status['status'] == 'cancelled':
            logger.info('job skipped (cancelled or missing): id=%s', job_id)
            return True

        await self._repo.mark_running(job_id)
        queries = await self._repo.get_queries(job_id)
        variables = await self._repo.get_variables(job_id)
        start, end = await self._repo.get_start_end(job_id)
        logger.info(
            'processing job: id=%s queries=%d start=%s end=%s',
            job_id,
            len(queries),
            start,
            end,
        )

        tasks = [
            self._run_query(
                job_id=job_id,
                sli_name=name,
                query_spec=spec,
                variables=variables,
                start=start,
                end=end,
            )
            for name, spec in queries.items()
        ]
        # return_exceptions keeps one unexpected escape from cancelling its siblings mid-flight;
        # _run_query already records per-SLI failures, so anything arriving here is a bug worth logging.
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)
        for sli_name, outcome in zip(queries, outcomes, strict=True):
            if isinstance(outcome, BaseException):
                logger.error('unhandled query error: job=%s sli=%s error=%r', job_id, sli_name, outcome)

        # Check if cancelled during processing
        final_status = await self._repo.get_status(job_id)
        if final_status and final_status['status'] != 'cancelled':
            await self._repo.mark_completed(job_id, self._settings.job_retention_seconds)
            logger.info('job completed: id=%s', job_id)
        else:
            logger.info('job cancelled: id=%s', job_id)

        return True

    async def run(self) -> None:
        """Main loop: continuously process jobs from the queue."""
        self._running = True
        logger.info('coordinator started, polling for jobs')
        while self._running:
            async with self._job_semaphore:
                try:
                    processed = await self.process_one()
                except Exception:
                    logger.exception('coordinator error processing job')
                    processed = False
            if not processed:
                await asyncio.sleep(0.1)

    def stop(self) -> None:
        """Signal the run loop to stop after the current job."""
        self._running = False
