"""arq worker job for evaluation execution."""

from __future__ import annotations

import uuid
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import Evaluation, SLIDefinition, SLODefinition
from app.modules.datasource.repository import DataSourceRepository
from app.modules.quality_gate.adapter_client import HttpAdapterClient
from app.modules.quality_gate.baseline_repository import BaselineRepository
from app.modules.quality_gate.engine.criteria import aggregate_values
from app.modules.quality_gate.engine.evaluator import evaluate
from app.modules.quality_gate.engine.slo_models import SLO
from app.modules.quality_gate.engine.slo_parser import build_slo
from app.modules.quality_gate.engine.variables import build_variables, substitute_variables
from app.modules.quality_gate.repository import EvaluationRepository
from app.modules.quality_gate.sli_repository import SLIValueRepository
from app.modules.sli_registry.repository import SLIRepository
from app.modules.slo_registry.repository import SLORepository


class DefinitionLoadError(Exception):
    """SLO or SLI definition could not be loaded."""


async def _load_definitions(
    session: AsyncSession,
    ev: Evaluation,
) -> tuple[SLODefinition, SLIDefinition]:
    """Load SLO and SLI definitions for the evaluation.

    Args:
        session: Active async DB session.
        ev: Evaluation row providing slo_name/version and sli_name/version.

    Returns:
        (slo_def, sli_def) tuple on success.

    Raises:
        DefinitionLoadError: If any required definition is missing.
    """
    if ev.slo_name is None or ev.slo_version is None:
        raise DefinitionLoadError("evaluation has no slo_name or slo_version")
    slo_def = await SLORepository(session).get_version(ev.slo_name, ev.slo_version)
    if slo_def is None:
        raise DefinitionLoadError(f"slo '{ev.slo_name}' v{ev.slo_version} not found")

    if ev.sli_name is None or ev.sli_version is None:
        raise DefinitionLoadError("evaluation has no sli_name or sli_version")
    sli_def = await SLIRepository(session).get_version(ev.sli_name, ev.sli_version)
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
            ir["value"]
            for bev in baseline_evals
            for ir in (bev.indicator_results or [])
            if ir.get("metric") == metric_name and ir.get("value") is not None
        ]
        if vals:
            baselines[metric_name] = aggregate_values(vals, slo.comparison.aggregate_function)

    return baselines, compared_eval_ids


async def run_evaluation(
    session: AsyncSession,
    eval_id: uuid.UUID,
    *,
    worker_id: str | None = None,
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
    """
    repo = EvaluationRepository(session)
    await repo.mark_running(eval_id, worker_id)

    ev = await repo.get_by_id(eval_id)
    if ev is None:
        return

    # Load SLO + SLI definitions
    try:
        slo_def, sli_def = await _load_definitions(session, ev)
    except DefinitionLoadError as exc:
        await repo.mark_failed(eval_id, job_stats={"error": str(exc)})
        return

    slo = build_slo(
        objectives=[
            {
                "sli": obj.sli,
                "display_name": obj.display_name,
                "pass_criteria": obj.pass_criteria,
                "warning_criteria": obj.warning_criteria,
                "weight": obj.weight,
                "key_sli": obj.key_sli,
            }
            for obj in slo_def.objectives
        ],
        total_score_pass_pct=slo_def.total_score_pass_pct,
        total_score_warning_pct=slo_def.total_score_warning_pct,
        comparison=slo_def.comparison,
    )

    # Build variables and substitute into queries
    asset_snapshot: dict[str, Any] = ev.asset_snapshot or {}
    asset_labels: dict[str, Any] = asset_snapshot.get("tags", {})
    eval_metadata: dict[str, Any] = ev.evaluation_metadata or {}
    variables = build_variables(
        metadata={k: str(v) for k, v in eval_metadata.items()},
        asset_name=asset_snapshot.get("name"),
        evaluation_name=ev.evaluation_name,
        start=ev.period_start.isoformat(),
        end=ev.period_end.isoformat(),
    )
    for k, v in asset_labels.items():
        variables.setdefault(k, str(v))
    resolved_queries: dict[str, str] = {
        name: substitute_variables(tmpl, variables) for name, tmpl in sli_def.indicators.items()
    }

    # Query adapter
    if ev.data_source_name is None:
        await repo.mark_failed(eval_id, job_stats={"error": "evaluation has no data_source_name"})
        return
    ds = await DataSourceRepository(session).get_by_name(ev.data_source_name)
    if ds is None:
        await repo.mark_failed(
            eval_id, job_stats={"error": f"datasource '{ev.data_source_name}' not found"}
        )
        return

    try:
        adapter_client = HttpAdapterClient(
            timeout=get_settings().reliability.adapter_timeout_seconds,
        )
        metrics_fetched, fetch_errors = await adapter_client.query(
            adapter_url=ds.adapter_url,
            datasource_name=ds.name,
            queries=resolved_queries,
            start=ev.period_start.isoformat(),
            end=ev.period_end.isoformat(),
        )
    except httpx.ConnectError:
        await repo.mark_failed(
            eval_id, job_stats={"error": f"could not reach adapter at {ds.adapter_url}"}
        )
        return
    except httpx.TimeoutException:
        await repo.mark_failed(eval_id, job_stats={"error": "adapter query timed out"})
        return
    except httpx.HTTPStatusError as exc:
        await repo.mark_failed(
            eval_id, job_stats={"error": f"adapter returned {exc.response.status_code}"}
        )
        return

    # Resolve baselines (pin-aware) and evaluate
    baseline_repo = BaselineRepository(session)
    baselines, compared_eval_ids = await _resolve_baselines(
        baseline_repo=baseline_repo, slo=slo, ev=ev, indicator_names=list(sli_def.indicators)
    )
    eval_result = evaluate(slo, metrics_fetched, baselines, compared_eval_ids)

    # Serialize typed indicator results for JSONB storage
    indicator_dicts: list[dict[str, Any]] = [
        ir.model_dump() for ir in eval_result.indicator_results
    ]

    # Write results
    await repo.mark_completed(
        eval_id,
        result=eval_result.result,
        score=eval_result.score,
        indicator_results=indicator_dicts,
        slo_name=ev.slo_name,
        slo_version=ev.slo_version,
        job_stats={"fetch_errors": fetch_errors},
        compared_evaluation_ids=compared_eval_ids,
    )

    # Write SLI values to TimescaleDB hypertable
    sli_rows: list[dict[str, Any]] = [
        {
            "eval_id": eval_id,
            "eval_start": ev.period_start,
            "metric_name": ir.metric,
            "aggregation": "raw",
            "value": ir.value,
            "asset_name": asset_snapshot.get("name"),
            "evaluation_name": ev.evaluation_name,
            "os_tag": asset_labels.get("os"),
        }
        for ir in eval_result.indicator_results
        if ir.value is not None
    ]
    if sli_rows:
        sli_repo = SLIValueRepository(session)
        await sli_repo.write_sli_values(sli_rows)
