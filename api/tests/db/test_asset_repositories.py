"""Integration tests for asset-family repositories."""

from __future__ import annotations

import pytest
import pytest_asyncio
from app.db.models import AssetType
from app.modules.assets.repository import (
    AssetGroupRepository,
    AssetGroupSLOLinkRepository,
    AssetRepository,
    AssetSLOLinkRepository,
    AssetTypeRepository,
)
from app.modules.assets.schemas import AssetGroupMemberCreate
from app.modules.slo_registry.repository import SLORepository
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture(autouse=True)
async def seed_asset_types(db_session: AsyncSession) -> None:
    """Seed the asset types required by FK constraints before each test.

    Migration 002 seeds default types including 'vm'. Only insert types
    that don't already exist to avoid unique-constraint violations.
    """
    for name in ('vm', 'sensor'):
        result = await db_session.execute(select(AssetType).where(AssetType.name == name))
        if result.scalar_one_or_none() is None:
            db_session.add(AssetType(name=name, is_default=False))
    await db_session.flush()


# ---------- AssetTypeRepository ----------


@pytest.mark.integration
async def test_asset_type_create_and_get(db_session: AsyncSession) -> None:
    repo = AssetTypeRepository(db_session)
    await repo.create('gpu', is_default=False)
    fetched = await repo.get_by_name('gpu')
    assert fetched is not None
    assert fetched.name == 'gpu'
    assert fetched.is_default is False


@pytest.mark.integration
async def test_asset_type_set_default_swaps(db_session: AsyncSession) -> None:
    repo = AssetTypeRepository(db_session)
    # Seed data already has "vm" as default — create non-default types and swap via set_default
    await repo.create('type-a', is_default=False)
    await repo.create('type-b', is_default=False)
    await repo.set_default('type-a')
    await repo.set_default('type-b')
    a = await repo.get_by_name('type-a')
    b = await repo.get_by_name('type-b')
    assert a is not None
    assert a.is_default is False
    assert b is not None
    assert b.is_default is True


@pytest.mark.integration
async def test_asset_type_delete_unused(db_session: AsyncSession) -> None:
    repo = AssetTypeRepository(db_session)
    await repo.create('removable', is_default=False)
    await repo.delete('removable')
    assert await repo.get_by_name('removable') is None


@pytest.mark.integration
async def test_asset_type_delete_in_use_raises(db_session: AsyncSession) -> None:
    type_repo = AssetTypeRepository(db_session)
    asset_repo = AssetRepository(db_session)
    await type_repo.create('in-use-type', is_default=False)
    await asset_repo.create('asset-using-type', type_name='in-use-type')
    with pytest.raises(HTTPException) as exc_info:
        await type_repo.delete('in-use-type')
    assert exc_info.value.status_code == 409


# ---------- AssetRepository ----------


@pytest.mark.integration
async def test_asset_create_and_get(db_session: AsyncSession) -> None:
    repo = AssetRepository(db_session)
    await repo.create(
        'vm-test-01',
        type_name='vm',
        tags={'dc': 'a'},
        variables={'host': 'vm-test-01.example.com'},
    )
    fetched = await repo.get_by_name('vm-test-01')
    assert fetched is not None
    assert fetched.tags == {'dc': 'a'}
    assert fetched.variables == {'host': 'vm-test-01.example.com'}
    assert fetched.type_name == 'vm'


@pytest.mark.integration
async def test_asset_update(db_session: AsyncSession) -> None:
    repo = AssetRepository(db_session)
    await repo.create('vm-update-01', type_name='vm')
    updated = await repo.update('vm-update-01', display_name='My VM', tags={'env': 'prod'})
    assert updated.display_name == 'My VM'
    assert updated.tags == {'env': 'prod'}


@pytest.mark.integration
async def test_asset_list_filter_by_type(db_session: AsyncSession) -> None:
    repo = AssetRepository(db_session)
    await repo.create('vm-filter-01', type_name='vm')
    await repo.create('sensor-filter-01', type_name='sensor')
    vms = await repo.list_all(type_name='vm')
    vm_names = {a.name for a in vms}
    assert 'vm-filter-01' in vm_names
    assert 'sensor-filter-01' not in vm_names


# ---------- AssetGroupRepository ----------


@pytest.mark.integration
async def test_asset_group_create_with_members(db_session: AsyncSession) -> None:
    asset_repo = AssetRepository(db_session)
    asset = await asset_repo.create('vm-group-member-01', type_name='vm')
    group_repo = AssetGroupRepository(db_session)
    group = await group_repo.create(
        'linux-boxes',
        members=[AssetGroupMemberCreate(asset_id=asset.id, weight=1.0)],
    )
    assert group.name == 'linux-boxes'
    assert len(group.members) == 1
    assert group.members[0].asset_name == 'vm-group-member-01'


@pytest.mark.integration
async def test_asset_group_add_remove_member(db_session: AsyncSession) -> None:
    asset_repo = AssetRepository(db_session)
    asset = await asset_repo.create('vm-addremove-01', type_name='vm')
    group_repo = AssetGroupRepository(db_session)
    group = await group_repo.create('test-group-addremove')
    group = await group_repo.add_member('test-group-addremove', asset.id, weight=2.0)
    assert len(group.members) == 1
    await group_repo.remove_member('test-group-addremove', asset.id)
    refetched = await group_repo.get_by_name('test-group-addremove')
    assert refetched is not None
    assert len(refetched.members) == 0


@pytest.mark.integration
async def test_asset_group_tree_top_level(db_session: AsyncSession) -> None:
    group_repo = AssetGroupRepository(db_session)
    await group_repo.create('parent-group-tree')
    child = await group_repo.create('child-group-tree')
    await group_repo.add_subgroup('parent-group-tree', child.id, weight=1.0)
    tree = await group_repo.get_tree()
    top_names = {g.name for g in tree.top_level}
    all_names = {g.name for g in tree.all_groups}
    assert 'parent-group-tree' in top_names
    assert 'child-group-tree' not in top_names  # it's a child, not top-level
    assert 'child-group-tree' in all_names


# ---------- AssetSLOLinkRepository ----------


@pytest.mark.integration
async def test_asset_slo_link_create_list_delete(db_session: AsyncSession) -> None:
    asset_repo = AssetRepository(db_session)
    asset = await asset_repo.create('vm-link-01', type_name='vm')
    repo = AssetSLOLinkRepository(db_session)
    await repo.create(
        asset_id=asset.id,
        link_name='compilation-check',
        slo_name='linux-compilation-slo',
        sli_name='linux-compilation-sli',
        data_source_name='prometheus-dc-a',
    )
    links = await repo.list_by_asset(asset.id)
    assert len(links) == 1
    assert links[0].link_name == 'compilation-check'
    await repo.delete(asset.id, 'compilation-check')
    links_after = await repo.list_by_asset(asset.id)
    assert len(links_after) == 0


@pytest.mark.integration
async def test_asset_group_slo_link_crud(db_session: AsyncSession) -> None:
    group_repo = AssetGroupRepository(db_session)
    group = await group_repo.create('grp-for-slo-link')
    link_repo = AssetGroupSLOLinkRepository(db_session)
    await link_repo.create(
        group_id=group.id,
        slo_name='linux-slo',
        sli_name='linux-sli',
        data_source_name='prometheus-dc-b',
    )
    links = await link_repo.list_by_group(group.id)
    assert len(links) == 1
    assert links[0].link_name == 'linux-slo--linux-sli'
    await link_repo.delete(group.id, 'linux-slo--linux-sli')
    links_after = await link_repo.list_by_group(group.id)
    assert len(links_after) == 0


@pytest.mark.integration
async def test_group_slo_link_duplicate_rejected(db_session: AsyncSession) -> None:
    group_repo = AssetGroupRepository(db_session)
    group = await group_repo.create('dup-link-grp')
    link_repo = AssetGroupSLOLinkRepository(db_session)
    await link_repo.create(
        group_id=group.id,
        slo_name='my-slo',
        sli_name='sli-a',
        data_source_name='ds-1',
    )
    with pytest.raises(IntegrityError):
        await link_repo.create(
            group_id=group.id,
            slo_name='my-slo',
            sli_name='sli-b',
            data_source_name='ds-2',
        )


@pytest.mark.integration
async def test_group_slo_link_name_auto_generated(db_session: AsyncSession) -> None:
    group_repo = AssetGroupRepository(db_session)
    group = await group_repo.create('auto-name-grp')
    link_repo = AssetGroupSLOLinkRepository(db_session)
    link = await link_repo.create(
        group_id=group.id,
        slo_name='error-rate',
        sli_name='prom-sli',
        data_source_name='prod-prom',
    )
    assert link.link_name == 'error-rate--prom-sli'


@pytest.mark.integration
async def test_group_update_properties(db_session: AsyncSession) -> None:
    repo = AssetGroupRepository(db_session)
    await repo.create('upd-grp', display_name='Old Name')
    updated = await repo.update('upd-grp', display_name='New Name', description='desc')
    assert updated is not None
    assert updated.display_name == 'New Name'
    assert updated.description == 'desc'


@pytest.mark.integration
async def test_group_delete_keeps_slos(db_session: AsyncSession) -> None:
    repo = AssetGroupRepository(db_session)
    group = await repo.create('del-grp')
    link_repo = AssetGroupSLOLinkRepository(db_session)
    await link_repo.create(group_id=group.id, slo_name='keep-slo', sli_name='sli', data_source_name='ds')
    deleted = await repo.delete_group('del-grp', deactivate_slos=False)
    assert deleted is True
    assert await repo.get_by_name('del-grp') is None


@pytest.mark.integration
async def test_group_delete_deactivates_slos(db_session: AsyncSession) -> None:
    slo_repo = SLORepository(db_session)
    await slo_repo.create(
        name='deact-slo',
        objectives=[],
        total_score_pass_pct=90.0,
        total_score_warning_pct=75.0,
    )
    group_repo = AssetGroupRepository(db_session)
    group = await group_repo.create('deact-grp')
    link_repo = AssetGroupSLOLinkRepository(db_session)
    await link_repo.create(group_id=group.id, slo_name='deact-slo', sli_name='sli', data_source_name='ds')
    await group_repo.delete_group('deact-grp', deactivate_slos=True)
    slo = await slo_repo.get_latest('deact-slo')
    assert slo is None


# ---------- Task 2: AssetType rename ----------


@pytest.mark.integration
async def test_asset_type_rename(db_session: AsyncSession) -> None:
    repo = AssetTypeRepository(db_session)
    await repo.create('old-name', is_default=False)
    renamed = await repo.rename('old-name', 'new-name')
    assert renamed is not None
    assert renamed.name == 'new-name'
    # Old name gone
    assert await repo.get_by_name('old-name') is None


@pytest.mark.integration
async def test_asset_type_rename_not_found(db_session: AsyncSession) -> None:
    repo = AssetTypeRepository(db_session)
    result = await repo.rename('nonexistent', 'whatever')
    assert result is None


@pytest.mark.integration
async def test_asset_type_rename_duplicate(db_session: AsyncSession) -> None:
    repo = AssetTypeRepository(db_session)
    await repo.create('type-a', is_default=False)
    await repo.create('type-b', is_default=False)
    with pytest.raises(HTTPException) as exc_info:
        await repo.rename('type-a', 'type-b')
    assert exc_info.value.status_code == 409


# ---------- Task 3: Asset delete ----------


@pytest.mark.integration
async def test_asset_delete(db_session: AsyncSession) -> None:
    repo = AssetRepository(db_session)
    await repo.create('deletable-asset', type_name='vm')
    result = await repo.delete('deletable-asset')
    assert result is True
    assert await repo.get_by_name('deletable-asset') is None


@pytest.mark.integration
async def test_asset_delete_not_found(db_session: AsyncSession) -> None:
    repo = AssetRepository(db_session)
    result = await repo.delete('nonexistent')
    assert result is False


@pytest.mark.integration
async def test_asset_delete_removes_group_memberships(db_session: AsyncSession) -> None:
    asset_repo = AssetRepository(db_session)
    group_repo = AssetGroupRepository(db_session)
    asset = await asset_repo.create('member-asset', type_name='vm')
    await group_repo.create('test-group')
    await group_repo.add_member('test-group', asset.id)
    await asset_repo.delete('member-asset')
    refreshed = await group_repo.get_by_name('test-group')
    assert refreshed is not None
    assert len(refreshed.members) == 0


# ---------- Task 4: Asset count ----------


@pytest.mark.integration
async def test_asset_type_list_includes_count(db_session: AsyncSession) -> None:
    type_repo = AssetTypeRepository(db_session)
    asset_repo = AssetRepository(db_session)
    await type_repo.create('counted-type', is_default=False)
    await asset_repo.create('a1', type_name='counted-type')
    await asset_repo.create('a2', type_name='counted-type')
    counts = await type_repo.get_asset_counts()
    assert counts['counted-type'] == 2


# ---------- Task 5: Tag autocomplete ----------


@pytest.mark.integration
async def test_tag_keys_aggregation(db_session: AsyncSession) -> None:
    repo = AssetRepository(db_session)
    await repo.create('lk1', type_name='vm', tags={'os': 'linux', 'env': 'prod'})
    await repo.create('lk2', type_name='vm', tags={'os': 'windows', 'env': 'staging'})
    await repo.create('lk3', type_name='vm', tags={'os': 'linux'})
    keys = await repo.get_tag_keys()
    assert keys == {'os': 3, 'env': 2}


@pytest.mark.integration
async def test_tag_values_for_key(db_session: AsyncSession) -> None:
    repo = AssetRepository(db_session)
    await repo.create('lv1', type_name='vm', tags={'os': 'linux'})
    await repo.create('lv2', type_name='vm', tags={'os': 'linux'})
    await repo.create('lv3', type_name='vm', tags={'os': 'windows'})
    values = await repo.get_tag_values('os')
    assert values == {'linux': 2, 'windows': 1}
