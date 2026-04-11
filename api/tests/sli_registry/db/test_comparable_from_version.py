"""Integration tests for comparable_from_version on SLI and SLO definitions."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from tropek.modules.sli_registry.params import SLICreateParams
from tropek.modules.sli_registry.repository import SLIRepository
from tropek.modules.slo_registry.params import SLOCreateParams, SLOObjectiveParams
from tropek.modules.slo_registry.repository import SLORepository

_OBJECTIVES = [SLOObjectiveParams(sli='cpu_usage', pass_threshold=['<90'], weight=1)]


@pytest.mark.integration
async def test_sli_first_version_defaults_to_one(db_session: AsyncSession) -> None:
    repo = SLIRepository(db_session)
    sli = await repo.create(
        SLICreateParams(name='test-sli-cfv', indicators={'cpu': 'avg(cpu_usage)'}, adapter_type='prometheus')
    )
    assert sli.version == 1
    assert sli.comparable_from_version == 1


@pytest.mark.integration
async def test_sli_second_version_defaults_to_previous(db_session: AsyncSession) -> None:
    repo = SLIRepository(db_session)
    await repo.create(
        SLICreateParams(name='test-sli-cfv-prev', indicators={'cpu': 'avg(cpu_usage)'}, adapter_type='prometheus')
    )
    sli_v2 = await repo.create(
        SLICreateParams(name='test-sli-cfv-prev', indicators={'cpu': 'avg(cpu_usage_v2)'}, adapter_type='prometheus')
    )
    assert sli_v2.version == 2
    assert sli_v2.comparable_from_version == 1


@pytest.mark.integration
async def test_sli_explicit_comparable_from_version(db_session: AsyncSession) -> None:
    repo = SLIRepository(db_session)
    await repo.create(
        SLICreateParams(name='test-sli-cfv-explicit', indicators={'cpu': 'avg(cpu_usage)'}, adapter_type='prometheus')
    )
    sli_v2 = await repo.create(
        SLICreateParams(
            name='test-sli-cfv-explicit',
            indicators={'cpu': 'avg(cpu_usage_v2)'},
            adapter_type='prometheus',
            comparable_from_version=2,
        )
    )
    assert sli_v2.version == 2
    assert sli_v2.comparable_from_version == 2


@pytest.mark.integration
async def test_slo_first_version_defaults_to_one(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    slo = await repo.create(SLOCreateParams(name='test-slo-cfv', objectives=_OBJECTIVES))
    assert slo.version == 1
    assert slo.comparable_from_version == 1


@pytest.mark.integration
async def test_slo_second_version_defaults_to_previous(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    await repo.create(SLOCreateParams(name='test-slo-cfv-prev', objectives=_OBJECTIVES))
    slo_v2 = await repo.create(SLOCreateParams(name='test-slo-cfv-prev', objectives=_OBJECTIVES))
    assert slo_v2.version == 2
    assert slo_v2.comparable_from_version == 1


@pytest.mark.integration
async def test_slo_explicit_comparable_from_version(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    await repo.create(SLOCreateParams(name='test-slo-cfv-explicit', objectives=_OBJECTIVES))
    slo_v2 = await repo.create(
        SLOCreateParams(
            name='test-slo-cfv-explicit',
            objectives=_OBJECTIVES,
            comparable_from_version=2,
        )
    )
    assert slo_v2.version == 2
    assert slo_v2.comparable_from_version == 2
