"""arq worker job for evaluation execution."""

from __future__ import annotations

import uuid
from typing import Any

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.redis_cache import RedisCache
from app.config import get_settings
from app.db.models import DataSource, Evaluation, SLIDefinition, SLODefinition
from app.modules.datasource.repository import DataSourceRepository
from app.modules.quality_gate.adapter_client import HttpAdapterClient
from app.modules.quality_gate.baseline_repository import BaselineRepository
from app.modules.quality_gate.engine.criteria import aggregate_values
from app.modules.quality_gate.engine.evaluator import evaluate
from app.modules.quality_gate.engine.slo_models import SLO
from app.modules.quality_gate.engine.slo_parser import build_slo
from app.modules.quality_gate.engine.variables import substitute_variables
from app.modules.quality_gate.evaluation_helpers import build_eval_variables as _build_eval_variables_shared
from app.modules.quality_gate.indicator_repository import IndicatorRepository
from app.modules.quality_gate.repository import EvaluationRepository
from app.modules.quality_gate.sli_repository import SLIValueRepository
from app.modules.sli_registry.repository import SLIRepository
from app.modules.slo_registry.repository import SLORepository

logger = structlog.get_logger()


class DefinitionLoadError(Exception):
    """SLO or SLI definition could not be loaded."""


async def _load_definitions(
    session: AsyncSession,
    ev: Evaluation,
    cache: RedisCache | None = None,
) -> tuple[SLODefinition, SLIDefinition]:
    """Load SLO and SLI definitions for the evaluation.

    Args:
        session: Active async DB session.
        ev: Evaluation row providing slo_name/version and sli_name/version.
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
    ev: Evaluation,
    indicator_names: list[str],
) -> tuple[dict[str, float | None], list[str]]:
    """Fetch baseline evaluations and aggregate per-metric values.

    Args:
        baseline_repo: Baseline repository for baseline queries.
        slo: Validated SLO model providing comparison config.
        ev: Current Evaluation ORM row (used for scoping).
        indicator_names: Metric names to collect baselines for.

    Returns:
        Tuple of (baselines dict, compared_eval_ids list).
    """
    baselines: dict[str, float | None] = {}
    compared_eval_ids: list[str] = []

    if slo.comparison.number_of_comparison_results <= 0:
        return baselines, compared_eval_ids

    baseline_evals = await baseline_repo.get_evaluation_baselines(
        asset_id=ev.asset_id,
        slo_name=ev.slo_name,
        period_start_before=ev.period_start,
        include_result_with_score=slo.comparison.include_result_with_score.value,
        limit=slo.comparison.number_of_comparison_results,
    )
    compared_eval_ids = [str(bev.id) for bev in baseline_evals]
    for metric_name in indicator_names:
        vals: list[float] = [
            float(row.value)
            for bev in baseline_evals
            for row in (bev.indicator_rows or [])
            if row.objective.sli == metric_name and row.value is not None
        ]
        if vals:
            baselines[metric_name] = aggregate_values(vals, slo.comparison.aggregate_function)

    return baselines, compared_eval_ids


def _build_eval_variables(
    ev: Evaluation,
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


async def _query_adapter_safe(
    log: structlog.stdlib.BoundLogger,
    repo: EvaluationRepository,
    eval_id: uuid.UUID,
    ds: DataSource,
    resolved_queries: dict[str, str],
    start: str,
    end: str,
) -> tuple[dict[str, float | None], dict[str, str]] | None:
    """Query adapter, mark failed on error. Returns None if query failed."""
    # Wrap bare query strings into v2 raw-mode query specs
    query_specs: dict[str, dict[str, str]] = {
        name: {'mode': 'raw', 'query': query} for name, query in resolved_queries.items()
    }
    try:
        adapter_client = HttpAdapterClient(
            timeout=get_settings().reliability.adapter_timeout_seconds,
        )
        return await adapter_client.query(
            adapter_url=ds.adapter_url,
            datasource_name=ds.name,
            queries=query_specs,
            variables={},
            start=start,
            end=end,
        )
    except httpx.ConnectError:
        log.exception('adapter unreachable', adapter_url=ds.adapter_url)
        await repo.mark_failed(eval_id, job_stats={'error': f'could not reach adapter at {ds.adapter_url}'})
        return None
    except httpx.TimeoutException:
        log.exception('adapter timeout', adapter_url=ds.adapter_url)
        await repo.mark_failed(eval_id, job_stats={'error': 'adapter query timed out'})
        return None
    except httpx.HTTPStatusError as exc:
        log.exception('adapter error', status=exc.response.status_code)
        await repo.mark_failed(eval_id, job_stats={'error': f'adapter returned {exc.response.status_code}'})
        return None


async def _write_indicator_rows(
    log: structlog.stdlib.BoundLogger,
    session: AsyncSession,
    eval_id: uuid.UUID,
    slo_def: SLODefinition,
    indicator_results: list[Any],
) -> None:
    """Write indicator results to the normalized indicator_results table."""
    indicator_repo = IndicatorRepository(session)
    obj_lookup = {obj.sli: obj.id for obj in slo_def.objectives}
    rows = []
    for ir in indicator_results:
        obj_id = obj_lookup.get(ir.metric)
        if obj_id is None:
            log.warning('no objective match for metric', metric=ir.metric)
            continue
        rows.append(
            {
                'evaluation_id': eval_id,
                'slo_objective_id': obj_id,
                'value': ir.value,
                'compared_value': ir.compared_value,
                'change_absolute': ir.change_absolute,
                'change_relative_pct': ir.change_relative_pct,
                'status': ir.status,
                'score': ir.score,
            }
        )
    if rows:
        await indicator_repo.bulk_insert(eval_id, rows)


async def run_evaluation(
    session: AsyncSession,
    eval_id: uuid.UUID,
    *,
    worker_id: str | None = None,
    cache: RedisCache | None = None,
) -> None:
    """Execute a single evaluation job.

    1. Mark running
    2. Load SLO + SLI definitions and build the SLO model
    3. Build variables and substitute into SLI queries
    4. Query adapter
    5. Resolve baselines (pin-aware)
    6. Evaluate
    7. Write results

    Args:
        session: Async SQLAlchemy session (injected by arq worker context).
        eval_id: UUID of the Evaluation row to execute.
        worker_id: Optional identifier of the worker process for observability.
        cache: Optional Redis cache for repository lookups.
    """
    log = logger.bind(evaluation_id=str(eval_id), worker_id=worker_id)
    log.info('evaluation started')

    repo = EvaluationRepository(session)
    await repo.mark_running(eval_id, worker_id)

    ev = await repo.get_by_id(eval_id)
    if ev is None:
        log.error('evaluation not found, cannot proceed')
        return

    # Deduplication guard — skip if already processed
    if ev.status not in ('pending', 'running'):
        log.warning(
            'evaluation already processed, skipping',
            status=ev.status,
        )
        return

    # Load SLO + SLI definitions
    try:
        slo_def, sli_def = await _load_definitions(session, ev, cache=cache)
    except DefinitionLoadError as exc:
        log.warning('definitions not found', reason=str(exc))
        await repo.mark_failed(eval_id, job_stats={'error': str(exc)})
        return

    slo = build_slo(
        objectives=[
            {
                'sli': obj.sli,
                'display_name': obj.display_name,
                'pass_criteria': obj.pass_criteria,
                'warning_criteria': obj.warning_criteria,
                'weight': obj.weight,
                'key_sli': obj.key_sli,
            }
            for obj in slo_def.objectives
        ],
        total_score_pass_pct=slo_def.total_score_pass_pct,
        total_score_warning_pct=slo_def.total_score_warning_pct,
        comparison=slo_def.comparison,
    )

    # Build variables and substitute into queries
    asset_snapshot: dict[str, Any] = ev.asset_snapshot or {}
    variables = _build_eval_variables(ev, asset_snapshot, slo_def)
    resolved_queries: dict[str, str] = {
        name: substitute_variables(tmpl, variables) for name, tmpl in sli_def.indicators.items()
    }

    # Query adapter
    if ev.data_source_name is None:
        log.error('evaluation has no data_source_name')
        await repo.mark_failed(eval_id, job_stats={'error': 'evaluation has no data_source_name'})
        return
    ds = await DataSourceRepository(session).get_by_name(ev.data_source_name)
    if ds is None:
        log.error('datasource not found', datasource_name=ev.data_source_name)
        await repo.mark_failed(eval_id, job_stats={'error': f"datasource '{ev.data_source_name}' not found"})
        return

    log.info('querying adapter', adapter_url=ds.adapter_url, metric_count=len(resolved_queries))
    adapter_result = await _query_adapter_safe(
        log=log,
        repo=repo,
        eval_id=eval_id,
        ds=ds,
        resolved_queries=resolved_queries,
        start=ev.period_start.isoformat(),
        end=ev.period_end.isoformat(),
    )
    if adapter_result is None:
        return
    metrics_fetched, fetch_errors = adapter_result

    # Resolve baselines (pin-aware) and evaluate
    baseline_repo = BaselineRepository(session, cache=cache)
    baselines, compared_eval_ids = await _resolve_baselines(
        baseline_repo=baseline_repo, slo=slo, ev=ev, indicator_names=list(sli_def.indicators)
    )
    eval_result = evaluate(slo, metrics_fetched, baselines, compared_eval_ids)

    # Write results
    await repo.mark_completed(
        eval_id,
        result=eval_result.result,
        score=eval_result.score,
        slo_name=ev.slo_name,
        slo_version=ev.slo_version,
        job_stats={
            'fetch_errors': fetch_errors,
            'total_score_pass_pct': slo_def.total_score_pass_pct,
            'total_score_warning_pct': slo_def.total_score_warning_pct,
        },
        compared_evaluation_ids=compared_eval_ids,
    )

    # Write to normalized indicator_results table
    await _write_indicator_rows(log, session, eval_id, slo_def, eval_result.indicator_results)

    # Write SLI values to TimescaleDB hypertable
    sli_rows: list[dict[str, Any]] = [
        {
            'eval_id': eval_id,
            'eval_start': ev.period_start,
            'metric_name': ir.metric,
            'aggregation': 'raw',
            'value': ir.value,
            'asset_name': asset_snapshot.get('name'),
            'evaluation_name': ev.evaluation_name,
            'os_tag': asset_snapshot.get('tags', {}).get('os') or asset_snapshot.get('variables', {}).get('os'),
        }
        for ir in eval_result.indicator_results
        if ir.value is not None
    ]
    if sli_rows:
        sli_repo = SLIValueRepository(session)
        await sli_repo.write_sli_values(sli_rows)

    log.info('evaluation completed', result=eval_result.result, score=eval_result.score)
