"""Integration tests for EvaluationRepository.

Requires TEST_DATABASE_URL and a running TimescaleDB instance.
Run: uv run pytest api/tests/db/test_evaluation_repository.py -m integration -v
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from tropek.db.models import Asset, AssetType
from tropek.modules.quality_gate.repositories.annotation import AnnotationRepository
from tropek.modules.quality_gate.repositories.baseline import BaselineRepository
from tropek.modules.quality_gate.repositories.evaluation import EvaluationRepository
from tropek.modules.quality_gate.repositories.sli_value import SLIValueRepository
from tropek.modules.quality_gate.shared.params import EvalCreateParams

_START = datetime(2026, 3, 12, 10, 0, 0, tzinfo=UTC)
_END = datetime(2026, 3, 12, 10, 30, 0, tzinfo=UTC)


async def _create_asset(session: AsyncSession, name: str | None = None) -> uuid.UUID:
    """Insert an AssetType and Asset, returning the asset ID."""
    type_name = f'vm-{uuid.uuid4().hex[:8]}'
    session.add(AssetType(id=uuid.uuid4(), name=type_name))
    await session.flush()
    asset_id = uuid.uuid4()
    asset_name = name or f'asset-{asset_id.hex[:8]}'
    session.add(Asset(id=asset_id, name=asset_name, type_name=type_name))
    await session.flush()
    return asset_id


def _make_snapshot(os: str = 'windows-11', arch: str = 'x64') -> dict[str, str | dict[str, str]]:
    return {'name': 'vm-test-01', 'tags': {'os': os, 'arch': arch}}


@pytest.mark.integration
async def test_create_pending_returns_evaluation(db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    repo = EvaluationRepository(db_session)
    ev = await repo.create_pending(
        EvalCreateParams(
            evaluation_id=uuid.uuid4(),
            evaluation_name='compile-test',
            period_start=_START,
            period_end=_END,
            ingestion_mode='push',
            asset_snapshot=_make_snapshot(),
            variables={},
            asset_id=asset_id,
            slo_name='test-slo',
        )
    )
    assert ev.status == 'pending'
    assert ev.result is None
    assert ev.id is not None


@pytest.mark.integration
async def test_get_returns_evaluation(db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    repo = EvaluationRepository(db_session)
    ev = await repo.create_pending(
        EvalCreateParams(
            evaluation_id=uuid.uuid4(),
            evaluation_name='get-test',
            period_start=_START,
            period_end=_END,
            ingestion_mode='push',
            asset_snapshot=_make_snapshot(),
            variables={},
            asset_id=asset_id,
            slo_name='test-slo',
        )
    )
    fetched = await repo.get_by_id(ev.id)
    assert fetched is not None
    assert fetched.id == ev.id


@pytest.mark.integration
async def test_mark_completed_updates_fields(db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    repo = EvaluationRepository(db_session)
    ev = await repo.create_pending(
        EvalCreateParams(
            evaluation_id=uuid.uuid4(),
            evaluation_name='complete-test',
            period_start=_START,
            period_end=_END,
            ingestion_mode='push',
            asset_snapshot=_make_snapshot(),
            variables={},
            asset_id=asset_id,
            slo_name='test-slo',
        )
    )
    await repo.mark_completed(
        ev.id,
        result='pass',
        score=95.0,
    )
    fetched = await repo.get_by_id(ev.id)
    assert fetched is not None
    assert fetched.status == 'completed'
    assert fetched.result == 'pass'
    assert fetched.score == 95.0


@pytest.mark.integration
async def test_mark_running_sets_status(db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    repo = EvaluationRepository(db_session)
    ev = await repo.create_pending(
        EvalCreateParams(
            evaluation_id=uuid.uuid4(),
            evaluation_name='running-test',
            period_start=_START,
            period_end=_END,
            ingestion_mode='pull',
            asset_snapshot=_make_snapshot(),
            variables={},
            asset_id=asset_id,
            slo_name='test-slo',
        )
    )
    await repo.mark_running(ev.id)
    fetched = await repo.get_by_id(ev.id)
    assert fetched is not None
    assert fetched.status == 'running'


@pytest.mark.integration
async def test_list_evaluations_filters_by_name(db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    repo = EvaluationRepository(db_session)
    # Each eval needs a unique identity tuple, so vary period_start
    starts = [
        datetime(2026, 3, 12, 10, 0, 0, tzinfo=UTC),
        datetime(2026, 3, 12, 11, 0, 0, tzinfo=UTC),
        datetime(2026, 3, 12, 12, 0, 0, tzinfo=UTC),
    ]
    for n, s in zip(('alpha', 'alpha', 'beta'), starts, strict=True):
        await repo.create_pending(
            EvalCreateParams(
                evaluation_id=uuid.uuid4(),
                evaluation_name=n,
                period_start=s,
                period_end=_END,
                ingestion_mode='push',
                asset_snapshot=_make_snapshot(),
                variables={},
                asset_id=asset_id,
                slo_name='test-slo',
            )
        )
    results = await repo.list_evaluations(evaluation_name='alpha')
    assert len(results) == 2
    assert all(e.evaluation_name == 'alpha' for e in results)


@pytest.mark.integration
async def test_get_baselines_excludes_invalidated(db_session: AsyncSession) -> None:
    """Invalidated evaluations are excluded from baselines."""
    repo = EvaluationRepository(db_session)
    baseline_repo = BaselineRepository(db_session)
    asset_id = await _create_asset(db_session)

    ev1 = await repo.create_pending(
        EvalCreateParams(
            evaluation_id=uuid.uuid4(),
            evaluation_name='run-1',
            period_start=_START,
            period_end=_END,
            ingestion_mode='push',
            asset_snapshot=_make_snapshot(),
            variables={},
            asset_id=asset_id,
            slo_name='http-slo',
        )
    )
    await repo.mark_completed(
        ev1.id,
        result='pass',
        score=90.0,
        slo_name='http-slo',
    )

    ev2 = await repo.create_pending(
        EvalCreateParams(
            evaluation_id=uuid.uuid4(),
            evaluation_name='run-2',
            period_start=_START,
            period_end=_END,
            ingestion_mode='push',
            asset_snapshot=_make_snapshot(),
            variables={},
            asset_id=asset_id,
            slo_name='http-slo',
        )
    )
    await repo.mark_completed(
        ev2.id,
        result='pass',
        score=90.0,
        slo_name='http-slo',
    )
    await repo.invalidate(ev2.id, note='bad data')

    baselines = await baseline_repo.get_evaluation_baselines(
        asset_id=asset_id,
        slo_name='http-slo',
        period_start_before=datetime(2027, 1, 1, tzinfo=UTC),
        include_result_with_score='all',
        limit=10,
    )
    assert len(baselines) == 1
    assert baselines[0].id == ev1.id


@pytest.mark.integration
async def test_add_and_list_annotations(db_session: AsyncSession, info_category_id: uuid.UUID) -> None:
    asset_id = await _create_asset(db_session)
    repo = EvaluationRepository(db_session)
    ann_repo = AnnotationRepository(db_session)
    ev = await repo.create_pending(
        EvalCreateParams(
            evaluation_id=uuid.uuid4(),
            evaluation_name='ann-test',
            period_start=_START,
            period_end=_END,
            ingestion_mode='push',
            asset_snapshot=_make_snapshot(),
            variables={},
            asset_id=asset_id,
            slo_name='test-slo',
        )
    )
    await ann_repo.add_annotation(
        ev.id, content='Defender update applied', author='ops', category_id=info_category_id
    )
    fetched = await repo.get_by_id(ev.id)
    assert fetched is not None
    assert len(fetched.annotations) == 1
    assert fetched.annotations[0].content == 'Defender update applied'


@pytest.mark.integration
async def test_hide_annotation(db_session: AsyncSession, info_category_id: uuid.UUID) -> None:
    asset_id = await _create_asset(db_session)
    repo = EvaluationRepository(db_session)
    ann_repo = AnnotationRepository(db_session)
    ev = await repo.create_pending(
        EvalCreateParams(
            evaluation_id=uuid.uuid4(),
            evaluation_name='hide-ann-test',
            period_start=_START,
            period_end=_END,
            ingestion_mode='push',
            asset_snapshot=_make_snapshot(),
            variables={},
            asset_id=asset_id,
            slo_name='test-slo',
        )
    )
    ann = await ann_repo.add_annotation(
        ev.id, content='wrong note', author='ops', category_id=info_category_id
    )
    hidden = await ann_repo.hide_annotation(ann.id, reason='typo', author='admin')
    assert hidden is not None
    assert hidden.hidden_at is not None
    assert hidden.hidden_by == 'admin'
    assert hidden.hidden_reason == 'typo'

    # Verify hidden annotation is excluded from counts
    _, _, count_map, _ = await repo.list_with_counts()
    assert count_map.get(ev.id, 0) == 0


@pytest.mark.integration
async def test_write_and_read_sli_values(db_session: AsyncSession) -> None:
    asset_id = await _create_asset(db_session)
    repo = EvaluationRepository(db_session)
    sli_val_repo = SLIValueRepository(db_session)
    ev = await repo.create_pending(
        EvalCreateParams(
            evaluation_id=uuid.uuid4(),
            evaluation_name='sli-test',
            period_start=_START,
            period_end=_END,
            ingestion_mode='push',
            asset_snapshot=_make_snapshot(),
            variables={},
            asset_id=asset_id,
            slo_name='test-slo',
        )
    )
    rows = [
        {
            'slo_evaluation_id': ev.id,
            'eval_start': _START,
            'metric_name': 'cpu_usage',
            'aggregation': 'avg',
            'value': 72.3,
            'asset_name': 'vm-test-01',
            'evaluation_name': 'sli-test',
            'os_tag': 'windows-11',
        }
    ]
    await sli_val_repo.write_sli_values(rows)
    stored = await sli_val_repo.get_sli_values_for_eval(ev.id)
    assert len(stored) == 1
    assert stored[0].metric_name == 'cpu_usage'
    assert stored[0].value == pytest.approx(72.3)


@pytest.mark.integration
async def test_get_baselines_excludes_null_sli_version_with_range(
    db_session: AsyncSession,
) -> None:
    """Evaluations with null sli_version are excluded when a range is specified."""
    repo = EvaluationRepository(db_session)
    baseline_repo = BaselineRepository(db_session)
    asset_id = await _create_asset(db_session)

    ev1 = await repo.create_pending(
        EvalCreateParams(
            evaluation_id=uuid.uuid4(),
            evaluation_name='daily-v2',
            period_start=_START,
            period_end=_END,
            ingestion_mode='push',
            asset_snapshot=_make_snapshot(),
            variables={},
            asset_id=asset_id,
            slo_name='http-slo',
            sli_version=2,
        )
    )
    await repo.mark_completed(
        ev1.id,
        result='pass',
        score=90.0,
        slo_name='http-slo',
    )

    ev2 = await repo.create_pending(
        EvalCreateParams(
            evaluation_id=uuid.uuid4(),
            evaluation_name='daily-null',
            period_start=_START,
            period_end=_END,
            ingestion_mode='push',
            asset_snapshot=_make_snapshot(),
            variables={},
            asset_id=asset_id,
            slo_name='http-slo',
        )
    )
    await repo.mark_completed(
        ev2.id,
        result='pass',
        score=90.0,
        slo_name='http-slo',
    )

    baselines = await baseline_repo.get_reeval_baselines(
        asset_id=asset_id,
        slo_name='http-slo',
        period_start_before=datetime(2027, 1, 1, tzinfo=UTC),
        include_result_with_score='all',
        limit=10,
        sli_version_range=(1, 3),
    )
    assert len(baselines) == 1
    assert baselines[0].sli_version == 2


@pytest.mark.integration
async def test_get_baselines_by_asset_and_slo(db_session: AsyncSession) -> None:
    """Baselines scoped by asset_id + slo_name, not by evaluation_name."""
    repo = EvaluationRepository(db_session)
    baseline_repo = BaselineRepository(db_session)
    asset_id = await _create_asset(db_session)
    other_asset_id = await _create_asset(db_session)

    for i, aid in enumerate((asset_id, asset_id, other_asset_id)):
        ev = await repo.create_pending(
            EvalCreateParams(
                evaluation_id=uuid.uuid4(),
                evaluation_name=f'run-{i}',
                period_start=_START,
                period_end=_END,
                ingestion_mode='push',
                asset_snapshot=_make_snapshot(),
                variables={},
                asset_id=aid,
                slo_name='http-slo',
            )
        )
        await repo.mark_completed(
            ev.id,
            result='pass',
            score=90.0,
            slo_name='http-slo',
        )

    baselines = await baseline_repo.get_evaluation_baselines(
        asset_id=asset_id,
        slo_name='http-slo',
        period_start_before=datetime(2027, 1, 1, tzinfo=UTC),
        include_result_with_score='all',
        limit=10,
    )
    assert len(baselines) == 2
    assert all(b.asset_id == asset_id for b in baselines)


@pytest.mark.integration
async def test_get_baselines_excludes_future_period_start(db_session: AsyncSession) -> None:
    """Baselines must have period_start strictly before the current evaluation."""
    repo = EvaluationRepository(db_session)
    baseline_repo = BaselineRepository(db_session)
    asset_id = await _create_asset(db_session)
    starts = [
        datetime(2026, 3, 10, tzinfo=UTC),
        datetime(2026, 3, 12, tzinfo=UTC),
        datetime(2026, 3, 14, tzinfo=UTC),
    ]
    for s in starts:
        ev = await repo.create_pending(
            EvalCreateParams(
                evaluation_id=uuid.uuid4(),
                evaluation_name='daily',
                period_start=s,
                period_end=s,
                ingestion_mode='push',
                asset_snapshot=_make_snapshot(),
                variables={},
                asset_id=asset_id,
                slo_name='http-slo',
            )
        )
        await repo.mark_completed(
            ev.id,
            result='pass',
            score=90.0,
            slo_name='http-slo',
        )

    baselines = await baseline_repo.get_evaluation_baselines(
        asset_id=asset_id,
        slo_name='http-slo',
        period_start_before=datetime(2026, 3, 12, tzinfo=UTC),
        include_result_with_score='all',
        limit=10,
    )
    assert len(baselines) == 1
    assert baselines[0].period_start == datetime(2026, 3, 10, tzinfo=UTC)


@pytest.mark.integration
async def test_get_baselines_with_tag_filters(db_session: AsyncSession) -> None:
    """Tag filters narrow baselines by variables JSONB values."""
    repo = EvaluationRepository(db_session)
    baseline_repo = BaselineRepository(db_session)
    asset_id = await _create_asset(db_session)

    for i, branch in enumerate(('main', 'main', 'feature-x')):
        ev = await repo.create_pending(
            EvalCreateParams(
                evaluation_id=uuid.uuid4(),
                evaluation_name=f'ci-run-{i}',
                period_start=_START,
                period_end=_END,
                ingestion_mode='push',
                asset_snapshot=_make_snapshot(),
                variables={'branch': branch},
                asset_id=asset_id,
                slo_name='http-slo',
            )
        )
        await repo.mark_completed(
            ev.id,
            result='pass',
            score=90.0,
            slo_name='http-slo',
        )

    baselines = await baseline_repo.get_reeval_baselines(
        asset_id=asset_id,
        slo_name='http-slo',
        period_start_before=datetime(2027, 1, 1, tzinfo=UTC),
        include_result_with_score='all',
        limit=10,
        tag_filters={'branch': 'main'},
    )
    assert len(baselines) == 2


@pytest.mark.integration
async def test_get_baselines_with_sli_version_range(db_session: AsyncSession) -> None:
    """Version range filter excludes evaluations outside the compatible range."""
    repo = EvaluationRepository(db_session)
    baseline_repo = BaselineRepository(db_session)
    asset_id = await _create_asset(db_session)

    for v in (1, 2, 3, 4):
        ev = await repo.create_pending(
            EvalCreateParams(
                evaluation_id=uuid.uuid4(),
                evaluation_name=f'daily-v{v}',
                period_start=_START,
                period_end=_END,
                ingestion_mode='push',
                asset_snapshot=_make_snapshot(),
                variables={},
                asset_id=asset_id,
                slo_name='http-slo',
                sli_version=v,
            )
        )
        await repo.mark_completed(
            ev.id,
            result='pass',
            score=90.0,
            slo_name='http-slo',
        )

    baselines = await baseline_repo.get_reeval_baselines(
        asset_id=asset_id,
        slo_name='http-slo',
        period_start_before=datetime(2027, 1, 1, tzinfo=UTC),
        include_result_with_score='all',
        limit=10,
        sli_version_range=(2, 4),
    )
    assert len(baselines) == 3
    for b in baselines:
        assert b.sli_version is not None
        assert b.sli_version >= 2


@pytest.mark.integration
async def test_get_baselines_restrict_to_ids(db_session: AsyncSession) -> None:
    """restrict_to_ids limits baselines to a specific set of evaluation IDs."""
    repo = EvaluationRepository(db_session)
    baseline_repo = BaselineRepository(db_session)
    asset_id = await _create_asset(db_session)

    eval_ids = []
    for i in range(3):
        ev = await repo.create_pending(
            EvalCreateParams(
                evaluation_id=uuid.uuid4(),
                evaluation_name=f'daily-{i}',
                period_start=_START,
                period_end=_END,
                ingestion_mode='push',
                asset_snapshot=_make_snapshot(),
                variables={},
                asset_id=asset_id,
                slo_name='http-slo',
            )
        )
        await repo.mark_completed(
            ev.id,
            result='pass',
            score=90.0,
            slo_name='http-slo',
        )
        eval_ids.append(ev.id)

    baselines = await baseline_repo.get_reeval_baselines(
        asset_id=asset_id,
        slo_name='http-slo',
        period_start_before=datetime(2027, 1, 1, tzinfo=UTC),
        include_result_with_score='all',
        limit=10,
        restrict_to_ids=eval_ids[:2],
    )
    assert len(baselines) == 2
    assert {b.id for b in baselines} == set(eval_ids[:2])


@pytest.mark.integration
async def test_create_pending_merges_asset_tags_into_variables(
    db_session: AsyncSession,
) -> None:
    """Asset tags become defaults in variables; caller values take precedence."""
    type_name = f'vm-{uuid.uuid4().hex[:8]}'
    db_session.add(AssetType(id=uuid.uuid4(), name=type_name))
    await db_session.flush()
    asset_id = uuid.uuid4()
    db_session.add(
        Asset(
            id=asset_id,
            name=f'tag-test-{asset_id.hex[:8]}',
            type_name=type_name,
            tags={'os': 'ubuntu-22', 'region': 'us-east-1', 'branch': 'main'},
        )
    )
    await db_session.flush()

    repo = EvaluationRepository(db_session)
    ev = await repo.create_pending(
        EvalCreateParams(
            evaluation_id=uuid.uuid4(),
            evaluation_name='tag-merge-test',
            period_start=_START,
            period_end=_END,
            ingestion_mode='push',
            asset_snapshot=_make_snapshot(),
            variables={'branch': 'feature-x', 'env': 'staging'},
            asset_id=asset_id,
            slo_name='test-slo',
        )
    )
    # Caller's "branch" wins over asset tag's "branch"
    assert ev.variables['branch'] == 'feature-x'
    # Asset tag "os" is merged as default
    assert ev.variables['os'] == 'ubuntu-22'
    assert ev.variables['region'] == 'us-east-1'
    # Caller's "env" is preserved
    assert ev.variables['env'] == 'staging'


@pytest.mark.integration
async def test_override_double_apply_preserves_original(db_session: AsyncSession) -> None:
    """Second override must NOT overwrite original_result from the first eval."""
    asset_id = await _create_asset(db_session)
    repo = EvaluationRepository(db_session)
    ev = await repo.create_pending(
        EvalCreateParams(
            evaluation_id=uuid.uuid4(),
            evaluation_name='override-test',
            period_start=_START,
            period_end=_END,
            ingestion_mode='push',
            asset_snapshot=_make_snapshot(),
            variables={},
            asset_id=asset_id,
            slo_name='test-slo',
        )
    )
    await repo.mark_completed(ev.id, result='fail', score=30.0, slo_name='test-slo')

    # First override: fail → pass
    await repo.override_status(ev.id, new_result='pass', reason='false alarm', author='alice')
    ev1 = await repo.get_by_id(ev.id)
    assert ev1.original_result == 'fail'
    assert ev1.result == 'pass'

    # Second override: pass → warning — original must still be "fail"
    await repo.override_status(ev.id, new_result='warning', reason='adjusted', author='bob')
    ev2 = await repo.get_by_id(ev.id)
    assert ev2.original_result == 'fail'  # NOT "pass"
    assert ev2.result == 'warning'
    assert ev2.override_author == 'bob'
