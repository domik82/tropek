"""Integration tests for AnnotationCategoryRepository."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from tropek.db.models import (
    Asset,
    AssetType,
    EvaluationRun,
)
from tropek.modules.quality_gate.repositories.annotation import AnnotationRepository
from tropek.modules.quality_gate.repositories.annotation_category import (
    AnnotationCategoryRepository,
    SystemCategoryError,
)

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture()
async def seeded_run_id(db_session: AsyncSession) -> uuid.UUID:
    """Create a minimal EvaluationRun and return its id for run-annotation tests."""
    type_name = f'vm-{uuid.uuid4().hex[:8]}'
    db_session.add(AssetType(id=uuid.uuid4(), name=type_name))
    await db_session.flush()
    asset_id = uuid.uuid4()
    db_session.add(Asset(id=asset_id, name=f'ann-cat-{asset_id.hex[:8]}', type_name=type_name))
    await db_session.flush()

    start = datetime(2026, 4, 1, 10, 0, 0, tzinfo=UTC)
    run = EvaluationRun(
        id=uuid.uuid4(),
        asset_id=asset_id,
        eval_name='daily',
        period_start=start,
        period_end=start + timedelta(hours=1),
        status='completed',
        result='pass',
        achieved_points=10,
        total_points=10,
    )
    db_session.add(run)
    await db_session.flush()
    return run.id


async def test_list_all_returns_seeded_rows(db_session: AsyncSession) -> None:
    repo = AnnotationCategoryRepository(db_session)
    rows = await repo.list_all()
    names = {r.name for r in rows}
    assert {'info', 'failure', 'investigation', 're-evaluation'} <= names


async def test_get_by_name_returns_category(db_session: AsyncSession) -> None:
    repo = AnnotationCategoryRepository(db_session)
    cat = await repo.get_by_name('info')
    assert cat is not None
    assert cat.is_system is False


async def test_create_adds_row(db_session: AsyncSession) -> None:
    repo = AnnotationCategoryRepository(db_session)
    created = await repo.create(name='release', label='Release', color='green', show_on_graph=True)
    assert created.id is not None
    assert created.is_system is False


async def test_update_modifies_fields(db_session: AsyncSession) -> None:
    repo = AnnotationCategoryRepository(db_session)
    created = await repo.create(name='incident', label='Incident', color='red', show_on_graph=True)
    updated = await repo.update(created.id, label='Inc', show_on_graph=False)
    assert updated.label == 'Inc'
    assert updated.show_on_graph is False


async def test_update_rejects_name_change_on_system(db_session: AsyncSession) -> None:
    repo = AnnotationCategoryRepository(db_session)
    re_eval = await repo.get_by_name('re-evaluation')
    assert re_eval is not None
    with pytest.raises(SystemCategoryError):
        await repo.update(re_eval.id, name='renamed')


async def test_delete_rejects_system_rows(db_session: AsyncSession) -> None:
    repo = AnnotationCategoryRepository(db_session)
    re_eval = await repo.get_by_name('re-evaluation')
    assert re_eval is not None
    with pytest.raises(SystemCategoryError):
        await repo.delete(re_eval.id)


async def test_delete_reassigns_referencing_annotations(db_session: AsyncSession, seeded_run_id: uuid.UUID) -> None:
    """Deleting a category with references must move them to 'info' and return the count."""
    repo = AnnotationCategoryRepository(db_session)
    dummy = await repo.create(name='temp', label='Temp', color='purple', show_on_graph=True)

    ann_repo = AnnotationRepository(db_session)
    await ann_repo.add_run_annotation(
        seeded_run_id,
        content='x',
        category_id=dummy.id,
    )
    await db_session.flush()

    reassigned = await repo.delete(dummy.id)
    assert reassigned == 1

    info = await repo.get_by_name('info')
    assert info is not None
    refreshed = await ann_repo.list_for_run(seeded_run_id)
    assert refreshed[0].category_id == info.id


async def test_delete_returns_zero_when_unused(db_session: AsyncSession) -> None:
    repo = AnnotationCategoryRepository(db_session)
    dummy = await repo.create(name='unused', label='Unused', color='pink', show_on_graph=True)
    reassigned = await repo.delete(dummy.id)
    assert reassigned == 0
