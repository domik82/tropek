"""Integration tests guarding indexes the hot read paths depend on.

Scope: the `db_engine` fixture builds the schema with `Base.metadata.create_all`,
so these assert that `models.py` declares each index — not that the Alembic
migrations create it. Model/migration drift is caught separately by
`alembic revision --autogenerate` reporting no changes.

These assert index existence rather than a query plan shape: on a small test
database the planner correctly prefers a sequential scan whether or not the
index is present, so a `Seq Scan` assertion would not track the defect it is
meant to guard.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


async def _index_names(db_session: AsyncSession, table_name: str) -> set[str]:
    result = await db_session.execute(
        text('SELECT indexname FROM pg_indexes WHERE tablename = :table_name'),
        {'table_name': table_name},
    )
    return {row.indexname for row in result}


async def test_slo_evaluations_evaluation_id_is_indexed(db_session: AsyncSession) -> None:
    """The grouped-heatmap child eager-load filters on `evaluation_id` — it must be indexed.

    Without this index `selectinload(EvaluationRun.slo_evaluations)` sequentially
    scans the whole table on every cold heatmap read.
    """
    assert 'idx_slo_evaluations_evaluation_id' in await _index_names(db_session, 'slo_evaluations')


async def test_indicator_results_slo_evaluation_id_is_indexed(db_session: AsyncSession) -> None:
    """The sibling child eager-load filters on `slo_evaluation_id` — it must be indexed."""
    assert 'idx_indicator_results_slo_evaluation' in await _index_names(db_session, 'indicator_results')
