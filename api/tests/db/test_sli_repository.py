"""Integration tests for SLIRepository."""

from __future__ import annotations

import pytest
from app.modules.sli_registry.params import SLICreateParams
from app.modules.sli_registry.repository import SLIRepository
from sqlalchemy.ext.asyncio import AsyncSession

_INDICATORS = {
    'response_time_p95': 'histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{instance="$vm_ip"}[5m]))',
    'cpu_usage_avg': 'avg_over_time(process_cpu_seconds_total{instance="$vm_ip"}[5m])',
}


@pytest.mark.integration
async def test_create_first_version(db_session: AsyncSession) -> None:
    repo = SLIRepository(db_session)
    sli = await repo.create(SLICreateParams(name='linux-sli', indicators=_INDICATORS, adapter_type='prometheus'))
    assert sli.version == 1
    assert sli.name == 'linux-sli'
    assert sli.indicators == _INDICATORS
    assert sli.active is True


@pytest.mark.integration
async def test_create_increments_version(db_session: AsyncSession) -> None:
    repo = SLIRepository(db_session)
    await repo.create(SLICreateParams(name='versioned-sli', indicators=_INDICATORS, adapter_type='prometheus'))
    v2 = await repo.create(
        SLICreateParams(name='versioned-sli', indicators={'cpu': 'some_query'}, adapter_type='prometheus')
    )
    assert v2.version == 2


@pytest.mark.integration
async def test_get_latest_returns_highest_version(db_session: AsyncSession) -> None:
    repo = SLIRepository(db_session)
    await repo.create(SLICreateParams(name='latest-sli', indicators={'a': 'q1'}, adapter_type='prometheus'))
    await repo.create(SLICreateParams(name='latest-sli', indicators={'a': 'q2'}, adapter_type='prometheus'))
    latest = await repo.get_latest('latest-sli')
    assert latest is not None
    assert latest.version == 2
    assert latest.indicators == {'a': 'q2'}


@pytest.mark.integration
async def test_get_version_returns_specific(db_session: AsyncSession) -> None:
    repo = SLIRepository(db_session)
    await repo.create(SLICreateParams(name='pinned-sli', indicators={'a': 'q1'}, adapter_type='prometheus'))
    await repo.create(SLICreateParams(name='pinned-sli', indicators={'a': 'q2'}, adapter_type='prometheus'))
    v1 = await repo.get_version('pinned-sli', 1)
    assert v1 is not None
    assert v1.indicators == {'a': 'q1'}


@pytest.mark.integration
async def test_get_latest_returns_none_for_unknown(db_session: AsyncSession) -> None:
    repo = SLIRepository(db_session)
    result = await repo.get_latest('does-not-exist')
    assert result is None


@pytest.mark.integration
async def test_deactivate_hides_from_get_latest(db_session: AsyncSession) -> None:
    repo = SLIRepository(db_session)
    await repo.create(SLICreateParams(name='gone-sli', indicators={'a': 'q1'}, adapter_type='prometheus'))
    await repo.deactivate('gone-sli')
    result = await repo.get_latest('gone-sli')
    assert result is None


@pytest.mark.integration
async def test_list_versions_newest_first(db_session: AsyncSession) -> None:
    repo = SLIRepository(db_session)
    await repo.create(SLICreateParams(name='history-sli', indicators={'a': 'q1'}, adapter_type='prometheus'))
    await repo.create(SLICreateParams(name='history-sli', indicators={'a': 'q2'}, adapter_type='prometheus'))
    versions = await repo.list_versions('history-sli')
    assert len(versions) == 2
    assert versions[0].version == 2
    assert versions[1].version == 1


@pytest.mark.integration
async def test_list_all_returns_latest_per_name(db_session: AsyncSession) -> None:
    repo = SLIRepository(db_session)
    await repo.create(SLICreateParams(name='sli-a', indicators={'x': 'q1'}, adapter_type='prometheus'))
    await repo.create(SLICreateParams(name='sli-a', indicators={'x': 'q2'}, adapter_type='prometheus'))
    await repo.create(SLICreateParams(name='sli-b', indicators={'y': 'q1'}, adapter_type='prometheus'))
    results = await repo.list_all()
    name_to_version = {r.name: r.version for r in results}
    assert name_to_version['sli-a'] == 2
    assert name_to_version['sli-b'] == 1


@pytest.mark.integration
async def test_create_with_adapter_type(db_session: AsyncSession) -> None:
    repo = SLIRepository(db_session)
    sli = await repo.create(
        SLICreateParams(
            name='typed-sli',
            indicators=_INDICATORS,
            adapter_type='prometheus',
        )
    )
    assert sli.adapter_type == 'prometheus'


@pytest.mark.integration
async def test_list_all_filters_by_adapter_type(db_session: AsyncSession) -> None:
    repo = SLIRepository(db_session)
    await repo.create(SLICreateParams(name='prom-sli', indicators={'a': 'q'}, adapter_type='prometheus'))
    await repo.create(SLICreateParams(name='dyna-sli', indicators={'b': 'q'}, adapter_type='dynatrace'))
    result = await repo.list_all(adapter_type='prometheus')
    assert len(result) == 1
    assert result[0].name == 'prom-sli'


@pytest.mark.integration
async def test_list_all_filters_by_tag(db_session: AsyncSession) -> None:
    repo = SLIRepository(db_session)
    await repo.create(
        SLICreateParams(name='sli-a', indicators={'m1': 'q1'}, adapter_type='prometheus', tags={'team': 'alpha'})
    )
    await repo.create(
        SLICreateParams(name='sli-b', indicators={'m2': 'q2'}, adapter_type='prometheus', tags={'team': 'beta'})
    )
    result = await repo.list_all(tag_key='team', tag_val='alpha')
    assert len(result) == 1
    assert result[0].name == 'sli-a'


@pytest.mark.integration
async def test_get_tag_keys(db_session: AsyncSession) -> None:
    repo = SLIRepository(db_session)
    await repo.create(
        SLICreateParams(
            name='sli-a', indicators={'m1': 'q1'}, adapter_type='prometheus', tags={'team': 'a', 'env': 'prod'}
        )
    )
    await repo.create(
        SLICreateParams(name='sli-b', indicators={'m2': 'q2'}, adapter_type='prometheus', tags={'env': 'staging'})
    )
    keys = await repo.get_tag_keys()
    assert keys['env'] == 2
    assert keys['team'] == 1


@pytest.mark.integration
async def test_get_tag_values(db_session: AsyncSession) -> None:
    repo = SLIRepository(db_session)
    await repo.create(
        SLICreateParams(name='sli-a', indicators={'m1': 'q1'}, adapter_type='prometheus', tags={'env': 'prod'})
    )
    await repo.create(
        SLICreateParams(name='sli-b', indicators={'m2': 'q2'}, adapter_type='prometheus', tags={'env': 'staging'})
    )
    values = await repo.get_tag_values('env')
    assert values['prod'] == 1
    assert values['staging'] == 1
