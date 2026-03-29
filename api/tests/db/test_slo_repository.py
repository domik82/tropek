"""Integration tests for SLORepository.

Requires TEST_DATABASE_URL and a running TimescaleDB instance.
Run: uv run pytest api/tests/db/test_slo_repository.py -m integration -v
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from app.db.session import get_session
from app.main import app
from app.modules.slo_registry.params import SLOCreateParams, SLOObjectiveParams
from app.modules.slo_registry.repository import SLORepository
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

OBJECTIVES_V1 = [SLOObjectiveParams(sli='m', pass_criteria=['<100'])]
OBJECTIVES_V2 = [SLOObjectiveParams(sli='m', pass_criteria=['<80'])]


@pytest_asyncio.fixture()
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    """Yield an httpx AsyncClient bound to the FastAPI app with test DB session."""

    async def _override_session() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = _override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.integration
async def test_create_first_version(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    slo = await repo.create(SLOCreateParams(name='my-slo', objectives=OBJECTIVES_V1, notes='Initial', author='alice'))
    assert slo.version == 1
    assert slo.name == 'my-slo'
    assert slo.author == 'alice'


@pytest.mark.integration
async def test_create_second_version_increments(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    await repo.create(SLOCreateParams(name='versioned-slo', objectives=OBJECTIVES_V1))
    v2 = await repo.create(
        SLOCreateParams(name='versioned-slo', objectives=OBJECTIVES_V2, notes='Tightened thresholds')
    )
    assert v2.version == 2


@pytest.mark.integration
async def test_get_latest_returns_highest_version(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    await repo.create(SLOCreateParams(name='latest-slo', objectives=OBJECTIVES_V1))
    await repo.create(SLOCreateParams(name='latest-slo', objectives=OBJECTIVES_V2))
    latest = await repo.get_latest('latest-slo')
    assert latest is not None
    assert latest.version == 2
    assert latest.total_score_pass_pct == 90.0
    assert latest.objectives[0].pass_criteria == ['<80']


@pytest.mark.integration
async def test_get_version_specific(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    await repo.create(SLOCreateParams(name='specific-slo', objectives=OBJECTIVES_V1))
    await repo.create(SLOCreateParams(name='specific-slo', objectives=OBJECTIVES_V2))
    v1 = await repo.get_version('specific-slo', 1)
    assert v1 is not None
    assert v1.objectives[0].pass_criteria == ['<100']


@pytest.mark.integration
async def test_list_versions_newest_first(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    await repo.create(SLOCreateParams(name='list-slo', objectives=OBJECTIVES_V1))
    await repo.create(SLOCreateParams(name='list-slo', objectives=OBJECTIVES_V2))
    versions = await repo.list_versions('list-slo')
    assert len(versions) == 2
    assert versions[0].version == 2
    assert versions[1].version == 1


@pytest.mark.integration
async def test_deactivate_hides_from_get_latest(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    await repo.create(SLOCreateParams(name='delete-slo', objectives=OBJECTIVES_V1))
    deleted = await repo.deactivate('delete-slo')
    assert deleted == 1
    result = await repo.get_latest('delete-slo')
    assert result is None


@pytest.mark.integration
async def test_get_latest_nonexistent_returns_none(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    result = await repo.get_latest('does-not-exist')
    assert result is None


@pytest.mark.integration
async def test_create_with_display_name_stores_and_retrieves(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    slo = await repo.create(
        SLOCreateParams(
            name='display-name-slo',
            objectives=OBJECTIVES_V1,
            display_name='My Test SLO',
            author='alice',
        )
    )
    assert slo.display_name == 'My Test SLO'
    fetched = await repo.get_latest('display-name-slo')
    assert fetched is not None
    assert fetched.display_name == 'My Test SLO'


@pytest.mark.integration
async def test_create_without_display_name_defaults_to_none(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    slo = await repo.create(SLOCreateParams(name='no-display-slo', objectives=OBJECTIVES_V1))
    assert slo.display_name is None
    fetched = await repo.get_latest('no-display-slo')
    assert fetched is not None
    assert fetched.display_name is None


@pytest.mark.integration
async def test_create_with_variables(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    slo = await repo.create(
        SLOCreateParams(
            name='slo-vars',
            objectives=[SLOObjectiveParams(sli='m1', pass_criteria=['<600'])],
            tags={'team': 'alpha'},
            variables={'aggregation_window': '5m'},
        )
    )
    assert slo.tags == {'team': 'alpha'}
    assert slo.variables == {'aggregation_window': '5m'}


@pytest.mark.integration
async def test_list_all_filters_by_tag(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    await repo.create(
        SLOCreateParams(
            name='slo-a', objectives=[SLOObjectiveParams(sli='m1', pass_criteria=['<600'])], tags={'env': 'prod'}
        )
    )
    await repo.create(
        SLOCreateParams(
            name='slo-b', objectives=[SLOObjectiveParams(sli='m2', pass_criteria=['<100'])], tags={'env': 'staging'}
        )
    )
    result = await repo.list_all(tag_key='env', tag_val='prod')
    assert len(result) == 1
    assert result[0].name == 'slo-a'


@pytest.mark.integration
async def test_get_tag_keys(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    await repo.create(
        SLOCreateParams(
            name='slo-a',
            objectives=[SLOObjectiveParams(sli='m1', pass_criteria=['<600'])],
            tags={'team': 'a', 'env': 'prod'},
        )
    )
    await repo.create(
        SLOCreateParams(
            name='slo-b',
            objectives=[SLOObjectiveParams(sli='m2', pass_criteria=['<100'])],
            tags={'env': 'staging'},
        )
    )
    keys = await repo.get_tag_keys()
    assert keys['env'] == 2
    assert keys['team'] == 1


@pytest.mark.integration
async def test_create_slo_with_sli_reference(async_client: AsyncClient) -> None:
    sli_resp = await async_client.post(
        '/sli-definitions',
        json={
            'name': 'test-sli-ref',
            'adapter_type': 'prometheus',
            'indicators': {'cpu': 'rate(cpu[5m])', 'mem': 'node_memory_bytes'},
        },
    )
    assert sli_resp.status_code == 201

    slo_resp = await async_client.post(
        '/slo-definitions',
        json={
            'name': 'test-slo-ref',
            'sli_name': 'test-sli-ref',
            'sli_version': 1,
            'objectives': [{'sli': 'cpu', 'pass_criteria': ['<80']}],
        },
    )
    assert slo_resp.status_code == 201
    data = slo_resp.json()
    assert data['sli_name'] == 'test-sli-ref'
    assert data['sli_version'] == 1
    assert data['kind'] == 'standard'


@pytest.mark.integration
async def test_create_slo_rejects_invalid_indicator(async_client: AsyncClient) -> None:
    await async_client.post(
        '/sli-definitions',
        json={
            'name': 'val-sli',
            'adapter_type': 'prometheus',
            'indicators': {'cpu': 'rate(cpu[5m])'},
        },
    )

    resp = await async_client.post(
        '/slo-definitions',
        json={
            'name': 'val-slo',
            'sli_name': 'val-sli',
            'sli_version': 1,
            'objectives': [{'sli': 'disk', 'pass_criteria': ['<80']}],
        },
    )
    assert resp.status_code == 422
    assert 'disk' in resp.json()['detail']


@pytest.mark.integration
async def test_list_slos_filter_by_kind(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    await repo.create(SLOCreateParams(name='std-slo-kind', objectives=OBJECTIVES_V1, kind='standard'))
    await repo.create(SLOCreateParams(name='tpl-slo-kind', objectives=OBJECTIVES_V1, kind='template'))

    std_results = await repo.list_all(kind='standard')
    assert any(s.name == 'std-slo-kind' for s in std_results)
    assert not any(s.name == 'tpl-slo-kind' for s in std_results)

    tpl_results = await repo.list_all(kind='template')
    assert any(s.name == 'tpl-slo-kind' for s in tpl_results)
    assert not any(s.name == 'std-slo-kind' for s in tpl_results)
