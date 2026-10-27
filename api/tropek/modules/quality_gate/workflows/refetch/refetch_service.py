"""Refetch service — resets stored SLO evaluations so the normal job fetches them again from the source."""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta

import structlog
from arq.connections import ArqRedis

from tropek.db.models import SLOEvaluation
from tropek.modules.change_points.repository import ChangePointRepository
from tropek.modules.common.exceptions import ConflictError, DomainValidationError, NotFoundError
from tropek.modules.quality_gate.repositories.evaluation import IN_PROGRESS_STATUSES, REFETCHABLE_STATUSES
from tropek.modules.quality_gate.schemas.refetch import (
    RefetchRequest,
    RefetchResponse,
    RefetchRunRequest,
)
from tropek.modules.quality_gate.shared.dependencies import QualityGateRepos
from tropek.modules.quality_gate.shared.params import RefetchScope

logger = structlog.get_logger()

# Seeded annotation category (migration 008) used for the run-level refetch note.
REFETCH_CATEGORY_NAME = 'refetch'
MAX_RANGE_DAYS = 400


def _validate_range(period_from: datetime, period_to: datetime) -> None:
    """Reject an inverted range or one wider than ``MAX_RANGE_DAYS``.

    Args:
        period_from: Inclusive start of the ``period_start`` range.
        period_to: Inclusive end of the ``period_start`` range.

    Raises:
        DomainValidationError: When ``period_to`` is before ``period_from`` or the range is too wide.
    """
    if period_to < period_from:
        raise DomainValidationError('to must not be before from')
    if period_to - period_from > timedelta(days=MAX_RANGE_DAYS):
        raise DomainValidationError(f'refetch range must not exceed {MAX_RANGE_DAYS} days')


async def refetch(request: RefetchRequest, repos: QualityGateRepos, arq_pool: ArqRedis) -> RefetchResponse:
    """Refetch the asset's SLO evaluations whose ``period_start`` lies in ``[from, to]``.

    Args:
        request: Asset, inclusive range and optional narrowing filters.
        repos: Repository bundle of the request.
        arq_pool: Queue the evaluation jobs are enqueued on.

    Returns:
        Counts and the affected run ids.

    Raises:
        DomainValidationError: When the range is inverted or wider than ``MAX_RANGE_DAYS``.
        NotFoundError: When the asset does not exist.
        ConflictError: When a matched row is pending or running; nothing is changed.
    """
    _validate_range(request.from_, request.to)
    asset = await repos.asset_repo.get_by_name(request.asset_name)
    if asset is None:
        raise NotFoundError('asset', request.asset_name)
    scope = RefetchScope(
        asset_id=asset.id,
        period_from=request.from_,
        period_to=request.to,
        evaluation_name=request.evaluation_name,
        slo_names=request.slo_names,
        only_failed=request.only_failed,
    )
    rows = await repos.eval_repo.list_for_refetch(scope)
    return await _refetch_rows(rows, request, repos, arq_pool)


async def refetch_run(
    run_id: uuid.UUID,
    request: RefetchRunRequest,
    repos: QualityGateRepos,
    arq_pool: ArqRedis,
) -> RefetchResponse:
    """Refetch the SLO evaluations of one evaluation run.

    Uses the same listing as the period refetch (so a failed row superseded by a retry is left
    alone), scoped to the run's asset and period and narrowed to the run's own rows.

    Args:
        run_id: The evaluation run whose SLO evaluations are refetched.
        request: ``only_failed``, ``dry_run``, ``reason`` and the requesting user.
        repos: Repository bundle of the request.
        arq_pool: Queue the evaluation jobs are enqueued on.

    Returns:
        Counts and the run id.

    Raises:
        NotFoundError: When the run does not exist.
        ConflictError: When a matched row is pending or running; nothing is changed.
    """
    run = await repos.eval_run_repo.get_by_id(run_id)
    if run is None:
        raise NotFoundError('evaluation run', str(run_id))
    scope = RefetchScope(
        asset_id=run.asset_id,
        period_from=run.period_start,
        period_to=run.period_end,
        evaluation_name=run.eval_name,
        evaluation_id=run_id,
        only_failed=request.only_failed,
    )
    rows = await repos.eval_repo.list_for_refetch(scope)
    return await _refetch_rows(rows, request, repos, arq_pool)


async def _refetch_rows(
    rows: list[SLOEvaluation],
    request: RefetchRequest | RefetchRunRequest,
    repos: QualityGateRepos,
    arq_pool: ArqRedis,
) -> RefetchResponse:
    """Plan the refetch of ``rows``; unless it is a dry run, reset the eligible rows and enqueue them."""
    eligible, response = _plan_refetch(rows, dry_run=request.dry_run)
    if request.dry_run or not eligible:
        return response
    await _reset_rows(eligible, reason=request.reason, requested_by=request.requested_by, repos=repos)
    await _commit_and_enqueue(eligible, response, repos, arq_pool, requested_by=request.requested_by)
    return response


def _plan_refetch(rows: list[SLOEvaluation], *, dry_run: bool) -> tuple[list[SLOEvaluation], RefetchResponse]:
    """Split the matched rows into the ones a refetch resets and build the response for them.

    Pure: reads the rows, writes nothing. The in-progress check runs here, before any write, so a 409
    leaves everything unchanged.

    Args:
        rows: SLO evaluations matched by the request's scope.
        dry_run: Echoed into the response.

    Returns:
        The eligible rows (terminal status) and the response describing them.

    Raises:
        ConflictError: When a matched row is pending or running.
    """
    in_progress = [row for row in rows if row.status in IN_PROGRESS_STATUSES]
    if in_progress:
        raise ConflictError('evaluation', str(in_progress[0].id), 'in progress')
    eligible = [row for row in rows if row.status in REFETCHABLE_STATUSES]
    response = RefetchResponse(
        matched=len(rows),
        refetched=len(eligible),
        run_ids=sorted({row.evaluation_id for row in eligible}),
        dry_run=dry_run,
    )
    return eligible, response


async def _commit_and_enqueue(
    eligible: list[SLOEvaluation],
    response: RefetchResponse,
    repos: QualityGateRepos,
    arq_pool: ArqRedis,
    *,
    requested_by: str | None,
) -> None:
    """Commit the reset, drop the rows' caches, then enqueue one job per row.

    Commit comes before touching Redis and the queue: a cache rebuilt between the delete and the commit
    would re-cache stale values, and a job must never start on uncommitted rows.

    Args:
        eligible: Rows reset by ``_reset_rows``.
        response: The planned response; its counts go into the success log.
        repos: Repository bundle of the request.
        arq_pool: Queue the evaluation jobs are enqueued on.
        requested_by: Requesting user, or ``None`` for ``system``; goes into the success log.
    """
    await repos.session.commit()
    await repos.eval_repo.invalidate_caches_for(eligible)
    if repos.trend_cache is not None:
        await repos.trend_cache.delete_many([row.id for row in eligible])
    for index, row in enumerate(eligible):
        try:
            await arq_pool.enqueue_job('run_evaluation_job', str(row.id))
        except Exception:
            # The rows are committed as pending; name the ones without a job so an operator can recover them.
            logger.exception(
                'refetch enqueue failed, evaluations left pending without a job',
                evaluation_ids=[str(pending.id) for pending in eligible[index:]],
            )
            raise
    logger.info(
        'evaluations refetched',
        refetched=response.refetched,
        run_count=len(response.run_ids),
        requested_by=requested_by,
    )


async def _reset_rows(
    eligible: list[SLOEvaluation],
    *,
    reason: str | None,
    requested_by: str | None,
    repos: QualityGateRepos,
) -> None:
    """Reset the rows in place, delete their runs' change points and annotate and re-open their runs.

    ``reset_for_refetch`` is a bulk UPDATE that expires ``job_stats`` on the in-session ``eligible`` rows, so
    never read ``row.job_stats`` after it.

    Args:
        eligible: Rows in a terminal status.
        reason: Free-text reason stored in the audit block and the run note.
        requested_by: Requesting user, or ``None`` for ``system``.
        repos: Repository bundle of the request.

    Raises:
        ConflictError: When a row left its terminal status after it was listed; nothing is committed.
    """
    category = await repos.category_repo.get_by_name(REFETCH_CATEGORY_NAME)
    if category is None:
        raise RuntimeError(f"seeded '{REFETCH_CATEGORY_NAME}' category missing")
    refetch_audit = {'requested_at': datetime.now(UTC).isoformat(), 'requested_by': requested_by, 'reason': reason}
    reset_ids = await repos.eval_repo.reset_for_refetch([row.id for row in eligible], refetch_audit=refetch_audit)
    if len(reset_ids) != len(eligible):
        # A concurrent refetch (or a job) re-opened a row after it was listed; resetting the rest and
        # enqueueing them again would run their jobs twice. Nothing is committed, so the request rolls back.
        raise ConflictError(
            'evaluation run', str(eligible[0].evaluation_id), 'an SLO evaluation changed status during the refetch'
        )

    await ChangePointRepository(repos.session).delete_for_run_slo_pairs(
        pairs=sorted({(row.evaluation_id, row.slo_name) for row in eligible})
    )
    await _reopen_and_annotate_runs(
        eligible, category_id=category.id, reason=reason, author=requested_by or 'system', repos=repos
    )


async def _reopen_and_annotate_runs(
    eligible: list[SLOEvaluation],
    *,
    category_id: uuid.UUID,
    reason: str | None,
    author: str,
    repos: QualityGateRepos,
) -> None:
    """Mark each affected run pending again and leave one refetch note on it.

    Args:
        eligible: Rows that were reset; their runs are re-opened.
        category_id: Annotation category of the refetch note.
        reason: Free-text reason appended to the note.
        author: Author of the note.
        repos: Repository bundle of the request.
    """
    note_suffix = f' — {reason}' if reason else ''
    for run_id, row_count in Counter(row.evaluation_id for row in eligible).items():
        await repos.eval_run_repo.mark_pending(run_id)
        await repos.annotation_repo.add_run_annotation(
            run_id,
            content=f'refetched from source: {row_count} SLO evaluation(s){note_suffix}',
            category_id=category_id,
            author=author,
        )
