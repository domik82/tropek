"""Shared helper functions for evaluation workflows.

Used by both the async worker and the SLO test-run service.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.modules.quality_gate.evaluation_engine.constants import AggregateFunction
from app.modules.quality_gate.evaluation_engine.criteria import aggregate_values
from app.modules.quality_gate.evaluation_engine.slo_models import SLO
from app.modules.quality_gate.evaluation_engine.slo_parser import build_slo
from app.modules.quality_gate.evaluation_engine.variables import build_variables


def build_eval_variables(
    *,
    asset_name: str | None,
    evaluation_name: str,
    start: str,
    end: str,
    asset_variables: dict[str, object] | None,
    asset_tags: dict[str, object] | None,
    slo_variables: dict[str, object] | None,
    eval_variables: dict[str, object] | None,
) -> dict[str, str]:
    """Build merged variables for query substitution.

    Merge priority (lowest → highest):
      reserved < asset.variables < asset.tags < slo.variables < eval.variables
    """
    variables = build_variables(
        metadata={},
        asset_name=asset_name,
        evaluation_name=evaluation_name,
        start=start,
        end=end,
    )
    # Add TROPEK-prefixed reserved vars for use in queries
    if asset_name:
        variables['TROPEK_ASSET'] = asset_name
    variables['TROPEK_EVALUATION'] = evaluation_name
    # Low priority: identity bindings from asset (setdefault = won't overwrite reserved)
    for k, v in (asset_variables or {}).items():
        variables.setdefault(k, str(v))
    for k, v in (asset_tags or {}).items():
        variables.setdefault(k, str(v))
    # High priority: SLO and per-run overrides (direct assignment = overwrites everything)
    for k, v in (slo_variables or {}).items():
        variables[k] = str(v)
    for k, v in (eval_variables or {}).items():
        variables[k] = str(v)
    return variables


def build_slo_model(slo_def: object) -> SLO:
    """Build the engine SLO model from a database SLO definition.

    Shared by the worker (first evaluation) and re-evaluator (re-scoring).
    Accepts any object with .objectives, .total_score_pass_threshold,
    .total_score_warning_threshold, and .comparison attributes.
    """
    objectives_dicts = [
        {
            'sli': obj.sli,
            'display_name': obj.display_name,
            'weight': obj.weight,
            'key_sli': obj.key_sli,
            'pass_threshold': list(obj.pass_threshold),
            'warning_threshold': list(obj.warning_threshold),
        }
        for obj in slo_def.objectives  # type: ignore[attr-defined]
    ]
    return build_slo(
        objectives=objectives_dicts,
        total_score_pass_threshold=slo_def.total_score_pass_threshold,  # type: ignore[attr-defined]
        total_score_warning_threshold=slo_def.total_score_warning_threshold,  # type: ignore[attr-defined]
        comparison=slo_def.comparison,  # type: ignore[attr-defined]
    )


def compute_baselines(
    baseline_evals: Sequence[object],
    aggregate_function: AggregateFunction,
) -> tuple[dict[str, float | None], list[str]]:
    """Aggregate baseline values from previous evaluations.

    Shared by the worker (first evaluation) and re-evaluator (re-scoring).

    Args:
        baseline_evals: List of SLOEvaluation-like objects with .id and .indicator_rows.
        aggregate_function: Aggregation function name (e.g. 'avg', 'p90').

    Returns:
        Tuple of (metric -> aggregated baseline value, list of compared eval ID strings).
    """
    if not baseline_evals:
        return {}, []

    compared_ids = [str(ev.id) for ev in baseline_evals]  # type: ignore[attr-defined]

    metric_values: dict[str, list[float]] = {}
    for ev in baseline_evals:
        for row in ev.indicator_rows or []:  # type: ignore[attr-defined]
            metric = row.objective.sli
            if metric is not None and row.value is not None:
                metric_values.setdefault(metric, []).append(float(row.value))

    baselines: dict[str, float | None] = {}
    for metric, values in metric_values.items():
        baselines[metric] = aggregate_values(values, aggregate_function)

    return baselines, compared_ids
