"""Background coordinator: picks jobs from queue, fans out queries."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from tropek_prometheus.config import Settings
from tropek_prometheus.core.prometheus_client import PrometheusQueryError
from tropek_prometheus.core.strategies.aggregated import AggregatedQueryStrategy
from tropek_prometheus.redis.repository import JobRepository

logger = logging.getLogger(__name__)

_IDLE_POLL_SECONDS = 0.1


class Coordinator:
    """Dequeues jobs and processes them with semaphore-limited concurrency.

    ``run`` keeps up to ``max_concurrent_jobs`` jobs in flight, each as its own task.
    ``max_concurrent_queries`` bounds the Prometheus queries running at once across all jobs of the
    process; a job's timeout keeps running while its queries wait for a slot.
    """

    def __init__(
        self,
        repo: JobRepository,
        settings: Settings,
        strategies: dict[str, Any],
    ) -> None:
        self._repo = repo
        self._settings = settings
        self._strategies = strategies
        self._query_semaphore = asyncio.Semaphore(settings.max_concurrent_queries)
        self._job_semaphore = asyncio.Semaphore(settings.max_concurrent_jobs)
        self._running = False
        self._running_jobs = 0
        self._job_tasks: set[asyncio.Task[None]] = set()

    @property
    def running_jobs(self) -> int:
        """Number of jobs currently being processed."""
        return self._running_jobs

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

        async with self._query_semaphore:
            # Check cancellation before executing
            current_status = await self._repo.get_status(job_id)
            if current_status and current_status['status'] == 'cancelled':
                return

            try:
                result = await strategy.execute(
                    sli_name=sli_name,
                    query_spec=query_spec,
                    variables=variables,
                    start=start,
                    end=end,
                )
            except Exception as query_exception:
                # A malformed spec must cost its own SLI, not the whole job: an exception escaping
                # here would abandon every sibling query and leave the job running.
                logger.exception(f'query failed: job={job_id} sli={sli_name}')
                transient = isinstance(query_exception, PrometheusQueryError) and query_exception.transient
                await self._repo.write_result(
                    job_id,
                    sli_name,
                    value=None,
                    success=False,
                    message=f'{type(query_exception).__name__}: {query_exception}',
                    query_executed=query_executed,
                    kind='transient' if transient else 'data',
                )
                return

            for name, outcome in result.indicators.items():
                await self._repo.write_result(
                    job_id,
                    name,
                    value=outcome.value,
                    success=outcome.error is None,
                    message=outcome.error or '',
                    query_executed=query_executed,
                    kind=outcome.error_kind or 'data',
                )

            if result.metadata is not None:
                await self._repo.write_metadata(job_id, sli_name, result.metadata.model_dump())

    async def _next_job(self) -> tuple[str, int] | None:
        """Dequeue the next job to run, expiring any cancelled or missing ones on the way.

        :returns: The job id and its timeout in seconds, or ``None`` when the queue is empty.
        :rtype: tuple[str, int] | None
        """
        while True:
            job_id = await self._repo.dequeue()
            if job_id is None:
                return None
            logger.info(f'dequeued job: id={job_id}')
            status = await self._repo.get_status(job_id)
            if status is not None and status['status'] != 'cancelled':
                return job_id, status['timeout_seconds']
            if status is not None:
                await self._repo.expire_job_keys(job_id, self._settings.job_retention_seconds)
            logger.info(f'job skipped (cancelled or missing): id={job_id}')

    async def _execute(self, job_id: str, timeout_seconds: int) -> None:
        """Process one job, counting it in ``running_jobs`` while it runs."""
        self._running_jobs += 1
        try:
            await self._process_job(job_id, timeout_seconds)
        finally:
            self._running_jobs -= 1

    async def process_one(self) -> bool:
        """Dequeue and process a single job in place. Returns True if a job was processed."""
        job = await self._next_job()
        if job is None:
            return False
        await self._execute(*job)
        return True

    async def _execute_and_release(self, job_id: str, timeout_seconds: int) -> None:
        """Run one job as a background task, then free its ``max_concurrent_jobs`` slot."""
        try:
            await self._execute(job_id, timeout_seconds)
        except Exception:
            logger.exception(f'coordinator error processing job: id={job_id}')
        finally:
            self._job_semaphore.release()

    async def _process_job(self, job_id: str, timeout_seconds: int) -> None:
        """Run every query of a dequeued job under the job's timeout and record the outcome.

        :param str job_id: Job to process.
        :param int timeout_seconds: The job's timeout in seconds.
        """
        await self._repo.mark_running(job_id)
        queries = await self._repo.get_queries(job_id)
        variables = await self._repo.get_variables(job_id)
        start, end = await self._repo.get_start_end(job_id)
        logger.info(f'processing job: id={job_id} queries={len(queries)} start={start} end={end}')

        finished_sli_names: set[str] = set()

        async def run_query_and_mark_finished(name: str, spec: dict[str, Any]) -> None:
            await self._run_query(
                job_id=job_id,
                sli_name=name,
                query_spec=spec,
                variables=variables,
                start=start,
                end=end,
            )
            finished_sli_names.add(name)

        tasks = [run_query_and_mark_finished(name, spec) for name, spec in queries.items()]
        # return_exceptions keeps one unexpected escape from cancelling its siblings mid-flight;
        # _run_query already records per-SLI failures, so anything arriving here is a bug worth logging.
        try:
            outcomes = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=timeout_seconds)
        except TimeoutError:
            # wait_for returns only after the cancelled gather has settled, so no _run_query is still
            # running and none can write a result over the ones recorded below.
            await self._fail_unfinished(job_id, queries, finished_sli_names, timeout_seconds)
            return
        for sli_name, outcome in zip(queries, outcomes, strict=True):
            if isinstance(outcome, BaseException):
                logger.error(f'unhandled query error: job={job_id} sli={sli_name} error={outcome!r}')

        # Check if cancelled during processing
        final_status = await self._repo.get_status(job_id)
        if final_status and final_status['status'] != 'cancelled':
            await self._repo.mark_completed(job_id, self._settings.job_retention_seconds)
            logger.info(f'job completed: id={job_id}')
        else:
            await self._repo.expire_job_keys(job_id, self._settings.job_retention_seconds)
            logger.info(f'job cancelled: id={job_id}')

    async def _fail_unfinished(
        self,
        job_id: str,
        queries: dict[str, dict[str, Any]],
        finished_sli_names: set[str],
        timeout_seconds: int,
    ) -> None:
        """Record a transient failure for every query that did not finish, then mark the job timed out.

        A job cancelled while it ran keeps its ``cancelled`` status and gets no synthetic results.

        :param str job_id: Job that exceeded its timeout.
        :param dict[str, dict[str, Any]] queries: All queries of the job, by SLI name.
        :param set[str] finished_sli_names: SLI names whose query ran to completion.
        :param int timeout_seconds: The timeout that was exceeded, in seconds.
        """
        current_status = await self._repo.get_status(job_id)
        if current_status is None or current_status['status'] == 'cancelled':
            if current_status is not None:
                await self._repo.expire_job_keys(job_id, self._settings.job_retention_seconds)
            logger.info(f'job cancelled: id={job_id}')
            return
        unfinished = [name for name in queries if name not in finished_sli_names]
        for name in unfinished:
            for indicator in AggregatedQueryStrategy.indicator_names(name, queries[name]):
                await self._repo.write_result(
                    job_id,
                    indicator,
                    value=None,
                    success=False,
                    message=f'job timed out after {timeout_seconds}s',
                    kind='transient',
                )
        await self._repo.mark_timed_out(job_id, self._settings.job_retention_seconds)
        logger.warning(f'job timed out: id={job_id} timeout={timeout_seconds}s unfinished={len(unfinished)}')

    async def run(self) -> None:
        """Main loop: start each dequeued job as a task, at most ``max_concurrent_jobs`` at once."""
        self._running = True
        logger.info('coordinator started, polling for jobs')
        while self._running:
            await self._job_semaphore.acquire()
            try:
                next_job = await self._next_job()
            except Exception:
                logger.exception('coordinator error dequeuing job')
                next_job = None
            if next_job is None:
                self._job_semaphore.release()
                await asyncio.sleep(_IDLE_POLL_SECONDS)
                continue
            job_id, job_timeout_seconds = next_job
            task = asyncio.create_task(self._execute_and_release(job_id, job_timeout_seconds))
            self._job_tasks.add(task)
            task.add_done_callback(self._job_tasks.discard)

    async def stop(self) -> None:
        """Stop the run loop and cancel the jobs still running, waiting until they have unwound."""
        self._running = False
        tasks = list(self._job_tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
