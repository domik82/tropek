"""Integration tests for AssignmentRepository."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from tropek.db.models import AssetType
from tropek.modules.assets.repository import AssetGroupRepository, AssetRepository
from tropek.modules.assignments.repository import AssignmentRepository
from tropek.modules.datasource.repository import DataSourceRepository
from tropek.modules.slo_groups.repository import SLOGroupRepository
from tropek.modules.slo_registry.params import SLOCreateParams, SLOObjectiveParams
from tropek.modules.slo_registry.repository import SLORepository

_OBJECTIVES = [SLOObjectiveParams(sli='cpu', pass_threshold=['<80'])]


@pytest_asyncio.fixture(autouse=True)
async def seed_asset_types(db_session: AsyncSession) -> None:
    """Ensure 'vm' asset type exists before each test."""
    result = await db_session.execute(select(AssetType).where(AssetType.name == 'vm'))
    if result.scalar_one_or_none() is None:
        db_session.add(AssetType(name='vm', is_default=False))
    await db_session.flush()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_asset(session: AsyncSession, name: str) -> object:
    return await AssetRepository(session).create(name, type_name='vm')


async def _make_datasource(session: AsyncSession, name: str) -> object:
    return await DataSourceRepository(session).create(
        name=name,
        adapter_type='prometheus',
        adapter_url='http://adapter:8081',
    )


async def _make_slo(session: AsyncSession, name: str) -> object:
    return await SLORepository(session).create(SLOCreateParams(name=name, objectives=_OBJECTIVES))


# ---------------------------------------------------------------------------
# SLO assignment CRUD
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_create_slo_assignment_for_asset(db_session: AsyncSession) -> None:
    asset = await _make_asset(db_session, 'assign-asset-1')
    slo = await _make_slo(db_session, 'assign-slo-1')
    ds = await _make_datasource(db_session, 'assign-ds-1')

    repo = AssignmentRepository(db_session)
    row = await repo.create_slo_assignment(
        asset_id=asset.id,
        asset_group_id=None,
        slo_definition_id=slo.id,
        slo_name=slo.name,
        data_source_id=ds.id,
    )

    assert row.asset_id == asset.id
    assert row.asset_group_id is None
    assert row.slo_name == 'assign-slo-1'
    assert row.slo_definition_id == slo.id
    assert row.data_source_id == ds.id


@pytest.mark.integration
async def test_create_slo_assignment_for_group(db_session: AsyncSession) -> None:
    ag = await AssetGroupRepository(db_session).create('assign-group-1')
    slo = await _make_slo(db_session, 'assign-slo-g1')
    ds = await _make_datasource(db_session, 'assign-ds-g1')

    repo = AssignmentRepository(db_session)
    row = await repo.create_slo_assignment(
        asset_id=None,
        asset_group_id=ag.id,
        slo_definition_id=slo.id,
        slo_name=slo.name,
        data_source_id=ds.id,
    )

    assert row.asset_group_id == ag.id
    assert row.asset_id is None
    assert row.slo_name == 'assign-slo-g1'


@pytest.mark.integration
async def test_slo_assignment_unique_per_slo_name(db_session: AsyncSession) -> None:
    asset = await _make_asset(db_session, 'assign-asset-uniq')
    ds = await _make_datasource(db_session, 'assign-ds-uniq')
    slo_v1 = await _make_slo(db_session, 'assign-slo-uniq')
    slo_v2 = await SLORepository(db_session).create(SLOCreateParams(name='assign-slo-uniq', objectives=_OBJECTIVES))

    repo = AssignmentRepository(db_session)
    await repo.create_slo_assignment(
        asset_id=asset.id,
        asset_group_id=None,
        slo_definition_id=slo_v1.id,
        slo_name=slo_v1.name,
        data_source_id=ds.id,
    )

    with pytest.raises(IntegrityError):
        await repo.create_slo_assignment(
            asset_id=asset.id,
            asset_group_id=None,
            slo_definition_id=slo_v2.id,
            slo_name=slo_v2.name,
            data_source_id=ds.id,
        )


@pytest.mark.integration
async def test_upgrade_slo_assignment(db_session: AsyncSession) -> None:
    asset = await _make_asset(db_session, 'assign-asset-upg')
    ds = await _make_datasource(db_session, 'assign-ds-upg')
    slo_v1 = await _make_slo(db_session, 'assign-slo-upg')
    slo_v2 = await SLORepository(db_session).create(SLOCreateParams(name='assign-slo-upg', objectives=_OBJECTIVES))

    repo = AssignmentRepository(db_session)
    row = await repo.create_slo_assignment(
        asset_id=asset.id,
        asset_group_id=None,
        slo_definition_id=slo_v1.id,
        slo_name=slo_v1.name,
        data_source_id=ds.id,
    )

    upgraded = await repo.upgrade_slo_assignment(row.id, slo_v2.id)

    assert upgraded is not None
    assert upgraded.slo_definition_id == slo_v2.id
    assert upgraded.slo_name == 'assign-slo-upg'  # name unchanged


@pytest.mark.integration
async def test_create_group_assignment(db_session: AsyncSession) -> None:
    asset = await _make_asset(db_session, 'assign-asset-ga')
    ds = await _make_datasource(db_session, 'assign-ds-ga')
    # Create a template SLO and SLO group
    slo_tpl = await SLORepository(db_session).create(
        SLOCreateParams(
            name='assign-tpl-$__gen_proc',
            objectives=_OBJECTIVES,
            kind='template',
            variables={'proc': '$__gen_proc'},
        )
    )
    sg = await SLOGroupRepository(db_session).create(
        name='assign-sg-1',
        template_slo_definition_id=slo_tpl.id,
        gen_variables={'proc': ['web']},
    )

    repo = AssignmentRepository(db_session)
    row = await repo.create_group_assignment(
        asset_id=asset.id,
        asset_group_id=None,
        slo_group_id=sg.id,
        data_source_id=ds.id,
    )

    assert row.slo_group_id == sg.id
    assert row.asset_id == asset.id
    assert row.asset_group_id is None


@pytest.mark.integration
async def test_resolve_direct_asset_assignment(db_session: AsyncSession) -> None:
    asset = await _make_asset(db_session, 'resolve-asset-1')
    ds = await _make_datasource(db_session, 'resolve-ds-1')
    slo = await _make_slo(db_session, 'resolve-slo-1')

    repo = AssignmentRepository(db_session)
    await repo.create_slo_assignment(
        asset_id=asset.id,
        asset_group_id=None,
        slo_definition_id=slo.id,
        slo_name=slo.name,
        data_source_id=ds.id,
    )

    resolved = await repo.resolve_for_asset(asset.id, [])

    assert len(resolved) == 1
    assert resolved[0].slo_name == 'resolve-slo-1'
    assert resolved[0].source == 'direct_asset'
    assert resolved[0].slo_definition_id == slo.id


@pytest.mark.integration
async def test_resolve_direct_asset_wins_over_group(db_session: AsyncSession) -> None:
    ag = await AssetGroupRepository(db_session).create('resolve-group-2')
    asset = await _make_asset(db_session, 'resolve-asset-2')
    ds = await _make_datasource(db_session, 'resolve-ds-2')

    slo_v1 = await _make_slo(db_session, 'resolve-slo-2')
    slo_v2 = await SLORepository(db_session).create(SLOCreateParams(name='resolve-slo-2', objectives=_OBJECTIVES))

    repo = AssignmentRepository(db_session)
    # Assign v1 to the group
    await repo.create_slo_assignment(
        asset_id=None,
        asset_group_id=ag.id,
        slo_definition_id=slo_v1.id,
        slo_name=slo_v1.name,
        data_source_id=ds.id,
    )
    # Assign v2 directly to the asset — should win
    await repo.create_slo_assignment(
        asset_id=asset.id,
        asset_group_id=None,
        slo_definition_id=slo_v2.id,
        slo_name=slo_v2.name,
        data_source_id=ds.id,
    )

    resolved = await repo.resolve_for_asset(asset.id, [ag.id])

    assert len(resolved) == 1
    assert resolved[0].slo_definition_id == slo_v2.id
    assert resolved[0].source == 'direct_asset'
