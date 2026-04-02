"""Integration tests for SLO display groups."""

from __future__ import annotations

import pytest
from app.modules.display_groups.repository import DisplayGroupRepository
from app.modules.slo_registry.params import SLOCreateParams, SLOObjectiveParams
from app.modules.slo_registry.repository import SLORepository
from sqlalchemy.ext.asyncio import AsyncSession

_OBJECTIVES = [SLOObjectiveParams(sli='cpu', pass_threshold=['<80'])]


async def _make_slo(session: AsyncSession, name: str) -> object:
    return await SLORepository(session).create(SLOCreateParams(name=name, objectives=_OBJECTIVES))


@pytest.mark.integration
async def test_create_display_group(db_session: AsyncSession) -> None:
    repo = DisplayGroupRepository(db_session)
    group = await repo.create(name='software-xyz', display_name='Software XYZ')
    assert group.name == 'software-xyz'
    assert group.parent_id is None


@pytest.mark.integration
async def test_create_nested_display_group(db_session: AsyncSession) -> None:
    repo = DisplayGroupRepository(db_session)
    parent = await repo.create(name='platform', display_name='Platform')
    child = await repo.create(
        name='platform-networking', display_name='Networking', parent_id=parent.id
    )
    assert child.parent_id == parent.id


@pytest.mark.integration
async def test_add_member(db_session: AsyncSession) -> None:
    await _make_slo(db_session, 'slo-cpu')
    repo = DisplayGroupRepository(db_session)
    group = await repo.create(name='compute', display_name='Compute')
    await repo.add_member(group.id, 'slo-cpu')
    members = await repo.list_members(group.id)
    assert 'slo-cpu' in members
