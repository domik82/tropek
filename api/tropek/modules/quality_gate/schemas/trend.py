"""Pydantic schemas for the per-SLO batched trend endpoint and its fragment cache."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, RootModel

from tropek.modules.quality_gate.schemas.evaluations import TrendPoint, TrendTargets

TREND_FRAGMENT_SCHEMA_VERSION = 1


class TrendFragmentPoint(BaseModel):
    """One indicator's value at one SLO-evaluation, cached inside a fragment.

    ``score`` is already normalized to the 0-100 percentage the trend endpoint
    returns (raw objective score / total objective weight * 100), and ``targets``
    is the ``IndicatorResultRow.targets`` payload — both stored verbatim so the
    projection matches the single-metric endpoint byte-for-byte.
    """

    metric: str
    value: float
    score: float
    result: str
    baseline: float | None = None
    targets: TrendTargets | None = None


class TrendColumnFragment(BaseModel):
    """One SLO's contribution to one EvaluationRun, cached independently in Redis.

    Cache key: ``trend:col:v{schema_version}:{slo_evaluation_id}`` with a TTL
    backstop. A full ``SloTrendsResponse`` for a range is assembled by projecting
    the fragments of every SLO-evaluation in that range. Change-points are NOT
    stored here; they are overlaid at read time.
    """

    schema_version: int = TREND_FRAGMENT_SCHEMA_VERSION
    slo_evaluation_id: uuid.UUID
    slo_name: str
    period_start: datetime
    period_end: datetime | None = None
    evaluation_name: str
    points: list[TrendFragmentPoint]


class SloTrendsResponse(RootModel[dict[str, list[TrendPoint]]]):
    """Batched trend response: metric name -> that indicator's ordered points."""
