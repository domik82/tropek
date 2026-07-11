"""Pure builders and projections for the per-SLO batched trend response.

No I/O. ``build_trend_fragment`` turns already-fetched DB rows into a cacheable
``TrendColumnFragment``; ``assemble_slo_trends`` projects a set of fragments into
the metric-keyed ``TrendPoint`` lists the endpoint returns. The score/baseline/
targets rules mirror ``TrendRepository.get_trend_by_domain`` exactly so the
batched endpoint is byte-for-byte equal to the single-metric endpoint.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from tropek.modules.change_points.repository import ChangePointKey
from tropek.modules.change_points.schemas import ChangePointMarker
from tropek.modules.quality_gate.schemas.evaluations import TrendPoint, TrendTargets
from tropek.modules.quality_gate.schemas.trend import TrendColumnFragment, TrendFragmentPoint


class TrendRow(BaseModel):
    """One indicator's raw DB values for one SLO-evaluation, pre-normalization."""

    metric: str
    value: float
    raw_score: float
    result: str
    compared_value: float | None = None
    targets: TrendTargets | None = None


def build_trend_fragment(
    *,
    slo_evaluation_id: uuid.UUID,
    slo_name: str,
    period_start: datetime,
    period_end: datetime | None,
    evaluation_name: str,
    total_weight: float,
    rows: list[TrendRow],
) -> TrendColumnFragment:
    """Build one cacheable fragment for a single SLO-evaluation."""
    points = [
        TrendFragmentPoint(
            metric=row.metric,
            value=row.value,
            score=round(row.raw_score / total_weight * 100, 2) if total_weight else 0,
            result=row.result,
            baseline=row.compared_value,
            targets=row.targets,
        )
        for row in rows
    ]
    return TrendColumnFragment(
        slo_evaluation_id=slo_evaluation_id,
        slo_name=slo_name,
        period_start=period_start,
        period_end=period_end,
        evaluation_name=evaluation_name,
        points=points,
    )


def _change_point_for(
    change_point_lookup: dict[ChangePointKey, Any] | None,
    slo_name: str,
    metric: str,
    period_start: datetime,
    period_end: datetime | None,
    evaluation_name: str,
) -> ChangePointMarker | None:
    if not change_point_lookup:
        return None
    key = ChangePointKey(slo_name, metric, period_start, period_end, evaluation_name)
    change_point = change_point_lookup.get(key)
    if change_point is None:
        return None
    # Duck-typed: builds an identical marker whether the value is a ChangePoint
    # DB entity (real path) or a ChangePointMarker (unit test). Mirrors the
    # field set the single-metric endpoint's _trend_change_point produces.
    return ChangePointMarker(
        direction=change_point.direction,
        change_relative_pct=change_point.change_relative_pct,
        transition=change_point.transition,
        change_absolute=change_point.change_absolute,
    )


def assemble_slo_trends(
    fragments: list[TrendColumnFragment],
    change_point_lookup: dict[ChangePointKey, Any] | None,
) -> dict[str, list[TrendPoint]]:
    """Project fragments into ``{metric: [TrendPoint ordered oldest-first]}``."""
    ordered_fragments = sorted(fragments, key=lambda fragment: (fragment.period_start, fragment.evaluation_name))
    by_metric: dict[str, list[TrendPoint]] = {}
    for fragment in ordered_fragments:
        for point in fragment.points:
            trend_point = TrendPoint(
                timestamp=fragment.period_start,
                value=point.value,
                score=point.score,
                eval_id=fragment.slo_evaluation_id,
                result=point.result,
                baseline=point.baseline,
                evaluation_name=fragment.evaluation_name,
                targets=point.targets,
                change_point=_change_point_for(
                    change_point_lookup,
                    fragment.slo_name,
                    point.metric,
                    fragment.period_start,
                    fragment.period_end,
                    fragment.evaluation_name,
                ),
            )
            by_metric.setdefault(point.metric, []).append(trend_point)
    return by_metric
