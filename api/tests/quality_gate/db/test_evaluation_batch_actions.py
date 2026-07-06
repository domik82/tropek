"""Integration tests for EvaluationRepository batch (bulk) action methods.

Requires TEST_DATABASE_URL and a running TimescaleDB instance.
Run: uv run pytest api/tests/quality_gate/db/test_evaluation_batch_actions.py -m integration -v
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tropek.db.models import Asset, AssetType, SLOEvaluation
from tropek.modules.quality_gate.repositories.evaluation import EvaluationRepository
from tropek.modules.quality_gate.shared.params import EvalCreateParams

_START = datetime(2026, 3, 12, 10, 0, 0, tzinfo=UTC)
_END = datetime(2026, 3, 12, 10, 30, 0, tzinfo=UTC)


async def _create_asset(session: AsyncSession) -> uuid.UUID:
    """Insert an AssetType and Asset, returning the asset ID."""
    type_name = f'vm-{uuid.uuid4().hex[:8]}'
    session.add(AssetType(id=uuid.uuid4(), name=type_name))
    await session.flush()
    asset_id = uuid.uuid4()
    session.add(Asset(id=asset_id, name=f'asset-{asset_id.hex[:8]}', type_name=type_name))
    await session.flush()
    return asset_id


async def _create_column(
    repo: EvaluationRepository,
    asset_id: uuid.UUID,
    slo_names: list[str],
    *,
    run_id: uuid.UUID | None = None,
    completed: bool = False,
    period_start: datetime = _START,
    period_end: datetime = _END,
) -> list[SLOEvaluation]:
    """Create one heatmap column: several SLO evaluations sharing a run id."""
    run_id = run_id or uuid.uuid4()
    evaluations: list[SLOEvaluation] = []
    for slo_name in slo_names:
        evaluation = await repo.create_pending(
            EvalCreateParams(
                evaluation_id=run_id,
                evaluation_name='nightly',
                period_start=period_start,
                period_end=period_end,
                ingestion_mode='push',
                asset_snapshot={'name': 'vm-test-01'},
                variables={},
                asset_id=asset_id,
                slo_name=slo_name,
            )
        )
        if completed:
            await repo.mark_completed(evaluation.id, result='pass', score=90.0, slo_name=slo_name)
        evaluations.append(evaluation)
    return evaluations


@pytest.mark.integration
async def test_invalidate_many_marks_only_selected(db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    repo = EvaluationRepository(db_session)
    column = await _create_column(repo, asset_id, ['slo-a', 'slo-b', 'slo-c'])

    affected = await repo.invalidate_many([column[0].id, column[1].id], note='bad data')

    assert {row.id for row in affected} == {column[0].id, column[1].id}
    refreshed = {evaluation.id: evaluation for evaluation in await repo.get_by_run_id(column[0].evaluation_id)}
    assert refreshed[column[0].id].invalidated is True
    assert refreshed[column[1].id].invalidated is True
    assert refreshed[column[2].id].invalidated is False  # sibling untouched


@pytest.mark.integration
async def test_restore_many_inverts_only_selected(db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    repo = EvaluationRepository(db_session)
    column = await _create_column(repo, asset_id, ['slo-a', 'slo-b', 'slo-c'])
    ids = [evaluation.id for evaluation in column]
    await repo.invalidate_many(ids, note='bad data')

    await repo.restore_many([ids[0], ids[1]])

    refreshed = {evaluation.id: evaluation for evaluation in await repo.get_by_run_id(column[0].evaluation_id)}
    assert refreshed[ids[0]].invalidated is False
    assert refreshed[ids[1]].invalidated is False
    assert refreshed[ids[2]].invalidated is True  # still invalidated
    # restore clears the note, not just the flag
    assert refreshed[ids[0]].invalidation_note is None
    assert refreshed[ids[2]].invalidation_note == 'bad data'  # untouched row keeps its note


@pytest.mark.integration
async def test_singular_invalidate_touches_single_row(db_session: AsyncSession) -> None:
    """Regression: the old whole-column (WHERE evaluation_id) behaviour is gone."""
    asset_id = await _create_asset(db_session)
    repo = EvaluationRepository(db_session)
    column = await _create_column(repo, asset_id, ['slo-a', 'slo-b'])

    await repo.invalidate(column[0].id, note='only me')

    refreshed = {evaluation.id: evaluation for evaluation in await repo.get_by_run_id(column[0].evaluation_id)}
    assert refreshed[column[0].id].invalidated is True
    assert refreshed[column[1].id].invalidated is False


@pytest.mark.integration
async def test_override_status_many_first_override_wins(db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    repo = EvaluationRepository(db_session)
    column = await _create_column(repo, asset_id, ['slo-a', 'slo-b'], completed=True)
    ids = [evaluation.id for evaluation in column]

    await repo.override_status_many(ids, new_result='fail', reason='first', author='alice')
    await repo.override_status_many(ids, new_result='warning', reason='second', author='bob')

    refreshed = {evaluation.id: evaluation for evaluation in await repo.get_by_run_id(column[0].evaluation_id)}
    for eval_id in ids:
        assert refreshed[eval_id].result == 'warning'
        assert refreshed[eval_id].original_result == 'pass'  # NOT 'fail'
        assert refreshed[eval_id].override_author == 'bob'


@pytest.mark.integration
async def test_override_status_many_skips_non_completed(db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    repo = EvaluationRepository(db_session)
    column = await _create_column(repo, asset_id, ['slo-a', 'slo-b'], completed=False)
    ids = [evaluation.id for evaluation in column]

    affected = await repo.override_status_many(ids, new_result='fail', reason='x', author='alice')

    assert affected == []  # pending rows are not eligible


@pytest.mark.integration
async def test_pin_baseline_many_one_active_pin_per_group(db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    repo = EvaluationRepository(db_session)
    # Two runs (columns) for the same (asset, slo-a) in distinct windows: pinning
    # the second must unpin the first, leaving exactly one active pin for the group.
    first = await _create_column(
        repo,
        asset_id,
        ['slo-a'],
        completed=True,
        period_start=datetime(2026, 3, 10, tzinfo=UTC),
        period_end=datetime(2026, 3, 10, tzinfo=UTC),
    )
    second = await _create_column(
        repo,
        asset_id,
        ['slo-a'],
        completed=True,
        period_start=datetime(2026, 3, 14, tzinfo=UTC),
        period_end=datetime(2026, 3, 14, tzinfo=UTC),
    )
    await repo.pin_baseline_many([first[0].id], reason='r1', author='alice')

    await repo.pin_baseline_many([second[0].id], reason='r2', author='bob')

    active_pins = await db_session.execute(
        select(SLOEvaluation.id).where(
            SLOEvaluation.asset_id == asset_id,
            SLOEvaluation.slo_name == 'slo-a',
            SLOEvaluation.baseline_pinned_at.is_not(None),
            SLOEvaluation.baseline_unpinned_at.is_(None),
        )
    )
    active_ids = list(active_pins.scalars().all())
    assert active_ids == [second[0].id]


@pytest.mark.integration
async def test_pin_baseline_many_dedupes_same_group(db_session: AsyncSession) -> None:
    """Two selected rows in the same (asset, slo) group → only the newest pinned."""
    asset_id = await _create_asset(db_session)
    repo = EvaluationRepository(db_session)
    run_id = uuid.uuid4()
    older = await repo.create_pending(
        EvalCreateParams(
            evaluation_id=run_id,
            evaluation_name='nightly',
            period_start=datetime(2026, 3, 10, tzinfo=UTC),
            period_end=datetime(2026, 3, 10, tzinfo=UTC),
            ingestion_mode='push',
            asset_snapshot={'name': 'vm-test-01'},
            variables={},
            asset_id=asset_id,
            slo_name='slo-a',
        )
    )
    await repo.mark_completed(older.id, result='pass', score=90.0, slo_name='slo-a')
    newer = await repo.create_pending(
        EvalCreateParams(
            evaluation_id=run_id,
            evaluation_name='nightly',
            period_start=datetime(2026, 3, 14, tzinfo=UTC),
            period_end=datetime(2026, 3, 14, tzinfo=UTC),
            ingestion_mode='push',
            asset_snapshot={'name': 'vm-test-01'},
            variables={},
            asset_id=asset_id,
            slo_name='slo-a',
        )
    )
    await repo.mark_completed(newer.id, result='pass', score=90.0, slo_name='slo-a')

    affected = await repo.pin_baseline_many([older.id, newer.id], reason='r', author='alice')

    assert {row.id for row in affected} == {newer.id}
    active_pins = await db_session.execute(
        select(SLOEvaluation.id).where(
            SLOEvaluation.asset_id == asset_id,
            SLOEvaluation.slo_name == 'slo-a',
            SLOEvaluation.baseline_pinned_at.is_not(None),
            SLOEvaluation.baseline_unpinned_at.is_(None),
        )
    )
    assert list(active_pins.scalars().all()) == [newer.id]


@pytest.mark.integration
async def test_restore_override_many_only_overridden_rows(db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    repo = EvaluationRepository(db_session)
    column = await _create_column(repo, asset_id, ['slo-a', 'slo-b'], completed=True)
    # Override only slo-a
    await repo.override_status_many([column[0].id], new_result='fail', reason='x', author='alice')

    affected = await repo.restore_override_many([column[0].id, column[1].id])

    assert {row.id for row in affected} == {column[0].id}  # slo-b had no override
    # restore_override_many sets result to another column (original_result); the
    # bulk UPDATE's synchronize_session='fetch' does not refresh the in-session
    # ORM object for a column-to-column SET, so read the columns directly (a Core
    # row, not the cached entity) for authoritative DB state.
    restored = (
        await db_session.execute(
            select(SLOEvaluation.result, SLOEvaluation.original_result).where(SLOEvaluation.id == column[0].id)
        )
    ).one()
    assert restored.result == 'pass'
    assert restored.original_result is None


@pytest.mark.integration
async def test_batch_methods_ignore_unknown_ids(db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    repo = EvaluationRepository(db_session)
    column = await _create_column(repo, asset_id, ['slo-a'])
    unknown = uuid.uuid4()

    affected = await repo.invalidate_many([column[0].id, unknown], note='bad')

    assert {row.id for row in affected} == {column[0].id}  # unknown id simply absent
