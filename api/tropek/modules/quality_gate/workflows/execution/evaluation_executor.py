"""arq worker job for evaluation execution."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import httpx
import structlog
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from tropek.cache.redis_cache import RedisCache
from tropek.db.models import DataSource, SLIDefinition, SLODefinition, SLOEvaluation
from tropek.modules.quality_gate.evaluation_engine.evaluator import evaluate
from tropek.modules.quality_gate.evaluation_engine.result_models import EvaluationResult, IndicatorResult
from tropek.modules.quality_gate.evaluation_engine.slo_models import SLO
from tropek.modules.quality_gate.evaluation_engine.variables import substitute_variables
from tropek.modules.quality_gate.repositories.baseline import BaselineRepository
from tropek.modules.quality_gate.repositories.evaluation import EvaluationRepository
from tropek.modules.quality_gate.repositories.indicator import IndicatorRepository, build_indicator_row_dicts
from tropek.modules.quality_gate.repositories.sli_value import SLIValueRepository
from tropek.modules.quality_gate.workflows.execution.adapter_client import HttpAdapterClient
from tropek.modules.quality_gate.workflows.execution.evaluation_helpers import (
    build_eval_variables as _build_eval_variables_shared,
)
from tropek.modules.quality_gate.workflows.execution.evaluation_helpers import (
    build_slo_model,
    compute_baselines,
)
from tropek.modules.sli_registry.repository import SLIRepository
from tropek.modules.slo_registry.repository import SLORepository

logger = structlog.get_logger()


class EvaluationSnapshot(BaseModel):
    """Detached snapshot of everything needed to run an evaluation without a DB session."""

    model_config = {'arbitrary_types_allowed': True}

    eval_id: uuid.UUID
    parent_run_id: uuid.UUID
    slo_name: str
    slo_version: int | None
    sli_name: str | None
    sli_version: int | None
    data_source_name: str | None
    evaluation_name: str
    period_start: datetime
    period_end: datetime
    asset_snapshot: dict[str, Any]
    asset_id: uuid.UUID
    variables: dict[str, Any]


class FetchAndEvaluateResult(BaseModel):
    """Output of phase 2, everything needed to write results."""

    model_config = {'arbitrary_types_allowed': True}

    eval_result: EvaluationResult
    metrics_fetched: dict[str, float | None]
    fetch_errors: dict[str, str]
    sli_metadata: dict[str, Any]
    baselines: dict[str, float | None]
    compared_eval_ids: list[str]


class DefinitionLoadError(Exception):
    """SLO or SLI definition could not be loaded."""


async def _load_definitions(
    session: AsyncSession,
    ev: SLOEvaluation | EvaluationSnapshot,
    cache: RedisCache | None = None,
) -> tuple[SLODefinition, SLIDefinition]:
    """Load SLO and SLI definitions for the evaluation.

    Args:
        session: Active async DB session.
        ev: Evaluation row or snapshot providing slo_name/version and sli_name/version.
        cache: Optional Redis cache for definition lookups.

    Returns:
        (slo_def, sli_def) tuple on success.

    Raises:
        DefinitionLoadError: If any required definition is missing.
    """
    if ev.slo_name is None or ev.slo_version is None:
        raise DefinitionLoadError('evaluation has no slo_name or slo_version')
    slo_def = await SLORepository(session, cache=cache).get_version(ev.slo_name, ev.slo_version)
    if slo_def is None:
        raise DefinitionLoadError(f"slo '{ev.slo_name}' v{ev.slo_version} not found")

    if ev.sli_name is None or ev.sli_version is None:
        raise DefinitionLoadError('evaluation has no sli_name or sli_version')
    sli_def = await SLIRepository(session, cache=cache).get_version(ev.sli_name, ev.sli_version)
    if sli_def is None:
        raise DefinitionLoadError(f"sli '{ev.sli_name}' v{ev.sli_version} not found")

    return slo_def, sli_def


async def _resolve_baselines(
    baseline_repo: BaselineRepository,
    slo: SLO,
    ev: SLOEvaluation | EvaluationSnapshot,
    indicator_names: list[str],
) -> tuple[dict[str, float | None], list[str]]:
    """Fetch baseline evaluations and aggregate per-metric values."""
    if slo.comparison.number_of_comparison_results <= 0:
        return {}, []

    baseline_evals = await baseline_repo.get_evaluation_baselines(
        asset_id=ev.asset_id,
        slo_name=ev.slo_name,
        period_start_before=ev.period_start,
        include_result_with_score=slo.comparison.include_result_with_score.value,
        limit=slo.comparison.number_of_comparison_results,
    )
    return compute_baselines(baseline_evals, slo.comparison.aggregate_function)


def _build_eval_variables(
    ev: SLOEvaluation | EvaluationSnapshot,
    asset_snapshot: dict[str, Any],
    slo_def: SLODefinition,
) -> dict[str, str]:
    """Build merged variables for query substitution.

    Merge priority: reserved < asset.variables < asset.tags < slo.variables < eval.variables.
    """
    return _build_eval_variables_shared(
        asset_name=asset_snapshot.get('name'),
        evaluation_name=ev.evaluation_name,
        start=ev.period_start.isoformat(),
        end=ev.period_end.isoformat(),
        asset_variables=asset_snapshot.get('variables'),
        asset_tags=asset_snapshot.get('tags'),
        slo_variables=slo_def.variables,
        eval_variables=ev.variables,
    )


def _build_query_specs(
    sli_def: SLIDefinition,
    resolved_queries: dict[str, str],
) -> dict[str, dict[str, Any]]:
    """Build adapter query specs from the SLI definition.

    For raw mode: wraps each resolved query string into {mode: raw, query: ...}.
    For aggregated mode: builds a single {mode: aggregated, ...} spec.
    """
    if sli_def.mode == 'aggregated':
        return {
            sli_def.name: {
                'mode': 'aggregated',
                'query_template': sli_def.query_template,
                'interval': sli_def.interval,
                'methods': sli_def.methods,
            }
        }
    return {name: {'mode': 'raw', 'query': query} for name, query in resolved_queries.items()}


async def _write_indicator_rows(
    log: structlog.stdlib.BoundLogger,
    session: AsyncSession,
    slo_evaluation_id: uuid.UUID,
    slo_def: SLODefinition,
    indicator_results: list[IndicatorResult],
) -> None:
    """Write indicator results to the normalized indicator_results table."""
    indicator_repo = IndicatorRepository(session)
    obj_lookup = {obj.sli: obj.id for obj in slo_def.objectives}
    rows = build_indicator_row_dicts(
        evaluation_id=slo_evaluation_id,
        indicator_results=indicator_results,
        obj_lookup=obj_lookup,
    )
    if rows:
        await indicator_repo.bulk_insert(slo_evaluation_id, rows)


def _build_sli_rows(
    *,
    eval_id: uuid.UUID,
    ev: SLOEvaluation | EvaluationSnapshot,
    sli_def: SLIDefinition,
    indicator_results: list[IndicatorResult],
    asset_snapshot: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build SLI value rows for TimescaleDB hypertable."""
    rows: list[dict[str, Any]] = []
    for ir in indicator_results:
        aggregation = 'raw'
        if sli_def.mode == 'aggregated' and '.' in ir.metric:
            aggregation = ir.metric.rsplit('.', 1)[1]
        rows.append(
            {
                'slo_evaluation_id': eval_id,
                'eval_start': ev.period_start,
                'metric_name': ir.metric,
                'aggregation': aggregation,
                'value': ir.value if ir.value is not None else 0.0,
                'asset_name': asset_snapshot.get('name'),
                'evaluation_name': ev.evaluation_name,
                'os_tag': asset_snapshot.get('tags', {}).get('os') or asset_snapshot.get('variables', {}).get('os'),
            }
        )
    return rows


def _log_adapter_response(
    log: structlog.stdlib.BoundLogger,
    metrics_fetched: dict[str, float | None],
    fetch_errors: dict[str, str],
    sli_metadata: dict[str, Any],
) -> None:
    """Log adapter response and override errored metrics to None."""
    log.info(
        'adapter raw response',
        values=metrics_fetched,
        errors=fetch_errors,
        metadata=sli_metadata,
    )
    for err_name in fetch_errors:
        metrics_fetched[err_name] = None
    if fetch_errors:
        log.warning(
            'metrics overridden to None due to adapter errors',
            overridden_metrics=list(fetch_errors.keys()),
        )


def _log_eval_result(
    log: structlog.stdlib.BoundLogger,
    eval_result: EvaluationResult,
    metrics_fetched: dict[str, float | None],
    baselines: dict[str, float | None],
) -> None:
    """Log per-indicator results and final score."""
    for ir in eval_result.indicator_results:
        log.info(
            'indicator result',
            metric=ir.metric,
            value=ir.value,
            status=ir.status,
            score=ir.score,
            compared_value=ir.compared_value,
            change_pct=ir.change_relative_pct,
        )
    log.info(
        'evaluation scored',
        result=eval_result.result,
        score=eval_result.score,
        indicator_count=len(eval_result.indicator_results),
        metrics_input=metrics_fetched,
        baselines=baselines,
    )


async def load_evaluation_snapshot(
    session: AsyncSession,
    eval_id: uuid.UUID,
    *,
    worker_id: str | None = None,
) -> EvaluationSnapshot | None:
    """Phase 1: mark running and build a detached snapshot.

    Marks the evaluation as running, loads the ORM row, and returns
    an ``EvaluationSnapshot`` that contains everything needed for
    phases 2 and 3 without a DB session.

    Returns None if the evaluation is not found or already processed.
    The caller should commit after this returns.

    Args:
        session: Active async DB session.
        eval_id: UUID of the Evaluation row to execute.
        worker_id: Optional identifier of the worker process for observability.
    """
    log = logger.bind(evaluation_id=str(eval_id), worker_id=worker_id)
    log.info('phase 1: loading evaluation snapshot', eval_id=str(eval_id))

    repo = EvaluationRepository(session)
    await repo.mark_running(eval_id, worker_id)

    ev = await repo.get_by_id(eval_id)
    if ev is None:
        log.error('evaluation not found, cannot proceed')
        return None

    # Deduplication guard — skip if already processed
    if ev.status not in ('pending', 'running'):
        log.warning(
            'evaluation already processed, skipping',
            status=ev.status,
        )
        return None

    return EvaluationSnapshot(
        eval_id=ev.id,
        parent_run_id=ev.evaluation_id,
        slo_name=ev.slo_name,
        slo_version=ev.slo_version,
        sli_name=ev.sli_name,
        sli_version=ev.sli_version,
        data_source_name=ev.data_source_name,
        evaluation_name=ev.evaluation_name,
        period_start=ev.period_start,
        period_end=ev.period_end,
        asset_snapshot=ev.asset_snapshot or {},
        asset_id=ev.asset_id,
        variables=ev.variables or {},
    )


async def fetch_and_evaluate(
    *,
    snapshot: EvaluationSnapshot,
    slo_def: SLODefinition,
    sli_def: SLIDefinition,
    datasource: DataSource,
    adapter_client: HttpAdapterClient,
    baseline_repo: BaselineRepository,
) -> FetchAndEvaluateResult | None:
    """Phase 2: query adapter, resolve baselines, and evaluate.

    Pure computation plus HTTP — no DB session needed.
    Returns None if the adapter query fails.

    Args:
        snapshot: Detached evaluation snapshot from phase 1.
        slo_def: SLO definition ORM object.
        sli_def: SLI definition ORM object.
        datasource: DataSource ORM object with adapter_url.
        adapter_client: HTTP adapter client for querying metrics.
        baseline_repo: Baseline repository for comparison queries.
    """
    log = logger.bind(evaluation_id=str(snapshot.eval_id))

    slo = build_slo_model(slo_def)

    # Build variables and query specs
    variables = _build_eval_variables(snapshot, snapshot.asset_snapshot, slo_def)

    # For raw mode, substitute variables into indicator queries locally
    resolved_queries: dict[str, str] = {}
    if sli_def.mode == 'raw':
        resolved_queries = {name: substitute_variables(tmpl, variables) for name, tmpl in sli_def.indicators.items()}

    query_specs = _build_query_specs(sli_def, resolved_queries)

    log.info(
        'phase 2: evaluation context',
        asset_name=snapshot.asset_snapshot.get('name'),
        evaluation_name=snapshot.evaluation_name,
        slo_name=snapshot.slo_name,
        slo_version=snapshot.slo_version,
        sli_name=snapshot.sli_name,
        sli_version=snapshot.sli_version,
        sli_mode=sli_def.mode,
        period_start=snapshot.period_start.isoformat(),
        period_end=snapshot.period_end.isoformat(),
        datasource=snapshot.data_source_name,
        query_specs=query_specs,
    )

    # Query adapter
    try:
        metrics_fetched, fetch_errors, sli_metadata = await adapter_client.query(
            adapter_url=datasource.adapter_url,
            datasource_name=datasource.name,
            queries=query_specs,
            variables=variables,
            start=snapshot.period_start.isoformat(),
            end=snapshot.period_end.isoformat(),
        )
    except (httpx.ConnectError, httpx.ReadError, httpx.TimeoutException, httpx.HTTPStatusError):
        log.exception('adapter query failed', adapter_url=datasource.adapter_url)
        return None

    _log_adapter_response(log, metrics_fetched, fetch_errors, sli_metadata)

    # Resolve baselines (pin-aware) and evaluate
    indicator_names = list(sli_def.indicators) if sli_def.mode == 'raw' else [obj.sli for obj in slo.objectives]
    baselines, compared_eval_ids = await _resolve_baselines(
        baseline_repo=baseline_repo,
        slo=slo,
        ev=snapshot,
        indicator_names=indicator_names,
    )
    eval_result = evaluate(slo, metrics_fetched, baselines, compared_eval_ids)

    _log_eval_result(log, eval_result, metrics_fetched, baselines)

    return FetchAndEvaluateResult(
        eval_result=eval_result,
        metrics_fetched=metrics_fetched,
        fetch_errors=fetch_errors,
        sli_metadata=sli_metadata,
        baselines=baselines,
        compared_eval_ids=compared_eval_ids,
    )


async def write_results(
    *,
    session: AsyncSession,
    snapshot: EvaluationSnapshot,
    slo_def: SLODefinition,
    fetch_result: FetchAndEvaluateResult,
    cache: RedisCache | None = None,
) -> None:
    """Phase 3a: write evaluation result and indicator rows.

    Writes mark_completed + indicator_results in one transaction.
    The sli_values hypertable write is split into write_sli_values_phase
    (separate transaction) to avoid deadlocks with TimescaleDB chunk locks.

    Caller should COMMIT after this returns.
    """
    log = logger.bind(evaluation_id=str(snapshot.eval_id))
    eval_result = fetch_result.eval_result

    achieved_points = sum(round(ir.score) for ir in eval_result.indicator_results)
    total_points = sum(int(obj.weight) for obj in slo_def.objectives)
    repo = EvaluationRepository(session, cache=cache)
    await repo.mark_completed(
        snapshot.eval_id,
        result=eval_result.result,
        score=eval_result.score,
        slo_name=snapshot.slo_name,
        slo_version=snapshot.slo_version,
        job_stats={
            'fetch_errors': fetch_result.fetch_errors,
            'total_score_pass_threshold': slo_def.total_score_pass_threshold,
            'total_score_warning_threshold': slo_def.total_score_warning_threshold,
            **({'sli_metadata': fetch_result.sli_metadata} if fetch_result.sli_metadata else {}),
        },
        compared_evaluation_ids=fetch_result.compared_eval_ids,
        achieved_points=achieved_points,
        total_points=total_points,
        asset_id=snapshot.asset_id,
    )

    await _write_indicator_rows(
        log,
        session,
        snapshot.eval_id,
        slo_def,
        eval_result.indicator_results,
    )

    log.info('phase 3a: results written', result=eval_result.result, score=eval_result.score)


async def write_sli_values_phase(
    *,
    session: AsyncSession,
    snapshot: EvaluationSnapshot,
    sli_def: SLIDefinition,
    fetch_result: FetchAndEvaluateResult,
) -> None:
    """Phase 3b: write SLI values to TimescaleDB hypertable.

    Separate transaction from write_results to avoid deadlocks caused by
    TimescaleDB chunk-level ShareUpdateExclusiveLock conflicting with FK
    locks from mark_completed on slo_evaluations.

    Caller should COMMIT after this returns.
    """
    sli_rows = _build_sli_rows(
        eval_id=snapshot.eval_id,
        ev=snapshot,
        sli_def=sli_def,
        indicator_results=fetch_result.eval_result.indicator_results,
        asset_snapshot=snapshot.asset_snapshot,
    )
    if sli_rows:
        sli_repo = SLIValueRepository(session)
        await sli_repo.write_sli_values(sli_rows)
