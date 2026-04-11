"""Repository for normalized indicator_results table."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import IndicatorResultRow
from app.modules.quality_gate.evaluation_engine.result_models import IndicatorResult


def build_indicator_row_dicts(
    *,
    evaluation_id: uuid.UUID,
    indicator_results: list[IndicatorResult],
    obj_lookup: dict[str, uuid.UUID],
) -> list[dict[str, Any]]:
    """Build row dicts from engine IndicatorResults for bulk_insert.

    Shared by the worker (first evaluation) and re-evaluator (re-scoring).
    """
    rows: list[dict[str, Any]] = []
    for ir in indicator_results:
        obj_id = obj_lookup.get(ir.metric)
        if obj_id is None:
            continue
        targets_dict: dict[str, Any] = {
            'pass': [t.model_dump() for t in ir.pass_targets],
        }
        if ir.warning_targets is not None:
            targets_dict['warn'] = [t.model_dump() for t in ir.warning_targets]
        rows.append(
            {
                'evaluation_id': evaluation_id,
                'slo_objective_id': obj_id,
                'value': ir.value,
                'compared_value': ir.compared_value,
                'change_absolute': ir.change_absolute,
                'change_relative_pct': ir.change_relative_pct,
                'status': ir.status,
                'score': ir.score,
                'targets': targets_dict,
            }
        )
    return rows


class IndicatorRepository:
    """CRUD for per-SLI evaluation results (normalized table)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def bulk_insert(
        self,
        slo_evaluation_id: uuid.UUID,
        rows: list[dict[str, Any]],
    ) -> None:
        """Insert indicator result rows for a single SLO evaluation."""
        for row in rows:
            self._session.add(
                IndicatorResultRow(
                    slo_evaluation_id=slo_evaluation_id,
                    slo_objective_id=row['slo_objective_id'],
                    value=row.get('value'),
                    compared_value=row.get('compared_value'),
                    change_absolute=row.get('change_absolute'),
                    change_relative_pct=row.get('change_relative_pct'),
                    status=row['status'],
                    score=row.get('score', 0.0),
                    targets=row.get('targets'),
                )
            )
        await self._session.flush()

    async def delete_for_evaluation(self, slo_evaluation_id: uuid.UUID) -> None:
        """Delete all indicator rows for a SLO evaluation (used by re-evaluation)."""
        await self._session.execute(
            delete(IndicatorResultRow).where(IndicatorResultRow.slo_evaluation_id == slo_evaluation_id)
        )
        await self._session.flush()
