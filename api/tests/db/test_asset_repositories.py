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
from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture(autouse=True)
async def seed_asset_types(db_session: AsyncSession) -> None:
    """Seed the asset types required by FK constraints before each test."""
    for name in ("vm", "sensor"):
        db_session.add(AssetType(name=name, is_default=False))
    await db_session.flush()


# ---------- AssetTypeRepository ----------


@pytest.mark.integration
async def test_asset_type_create_and_get(db_session: AsyncSession) -> None:
    repo = AssetTypeRepository(db_session)
    await repo.create("gpu", is_default=False)
    fetched = await repo.get_by_name("gpu")
    assert fetched is not None
    assert fetched.name == "gpu"
    assert fetched.is_default is False


@pytest.mark.integration
async def test_asset_type_set_default_swaps(db_session: AsyncSession) -> None:
    repo = AssetTypeRepository(db_session)
    await repo.create("type-a", is_default=True)
    await repo.create("type-b", is_default=False)
    await repo.set_default("type-b")
    a = await repo.get_by_name("type-a")
    b = await repo.get_by_name("type-b")
    assert a is not None
    assert a.is_default is False
    assert b is not None
    assert b.is_default is True


@pytest.mark.integration
async def test_asset_type_delete_unused(db_session: AsyncSession) -> None:
    repo = AssetTypeRepository(db_session)
    await repo.create("removable", is_default=False)
    await repo.delete("removable")
    assert await repo.get_by_name("removable") is None


@pytest.mark.integration
async def test_asset_type_delete_in_use_raises(db_session: AsyncSession) -> None:
    from fastapi import HTTPException

    type_repo = AssetTypeRepository(db_session)
    asset_repo = AssetRepository(db_session)
    await type_repo.create("in-use-type", is_default=False)
    await asset_repo.create("asset-using-type", type_name="in-use-type")
    with pytest.raises(HTTPException) as exc_info:
        await type_repo.delete("in-use-type")
    assert exc_info.value.status_code == 409


# ---------- AssetRepository ----------


@pytest.mark.integration
async def test_asset_create_and_get(db_session: AsyncSession) -> None:
    repo = AssetRepository(db_session)
    await repo.create("vm-test-01", type_name="vm", labels={"dc": "a"})
    fetched = await repo.get_by_name("vm-test-01")
    assert fetched is not None
    assert fetched.labels == {"dc": "a"}
    assert fetched.type_name == "vm"


@pytest.mark.integration
async def test_asset_update(db_session: AsyncSession) -> None:
    repo = AssetRepository(db_session)
    await repo.create("vm-update-01", type_name="vm")
    updated = await repo.update("vm-update-01", display_name="My VM", labels={"env": "prod"})
    assert updated.display_name == "My VM"
    assert updated.labels == {"env": "prod"}


@pytest.mark.integration
async def test_asset_list_filter_by_type(db_session: AsyncSession) -> None:
    repo = AssetRepository(db_session)
    await repo.create("vm-filter-01", type_name="vm")
    await repo.create("sensor-filter-01", type_name="sensor")
    vms = await repo.list_all(type_name="vm")
    vm_names = {a.name for a in vms}
    assert "vm-filter-01" in vm_names
    assert "sensor-filter-01" not in vm_names


# ---------- AssetGroupRepository ----------


@pytest.mark.integration
async def test_asset_group_create_with_members(db_session: AsyncSession) -> None:
    from app.modules.assets.schemas import AssetGroupMemberCreate

    asset_repo = AssetRepository(db_session)
    asset = await asset_repo.create("vm-group-member-01", type_name="vm")
    group_repo = AssetGroupRepository(db_session)
    group = await group_repo.create(
        "linux-boxes",
        members=[AssetGroupMemberCreate(asset_id=asset.id, weight=1.0)],
    )
    assert group.name == "linux-boxes"
    assert len(group.members) == 1
    assert group.members[0].asset_name == "vm-group-member-01"


@pytest.mark.integration
async def test_asset_group_add_remove_member(db_session: AsyncSession) -> None:
    asset_repo = AssetRepository(db_session)
    asset = await asset_repo.create("vm-addremove-01", type_name="vm")
    group_repo = AssetGroupRepository(db_session)
    group = await group_repo.create("test-group-addremove")
    group = await group_repo.add_member("test-group-addremove", asset.id, weight=2.0)
    assert len(group.members) == 1
    await group_repo.remove_member("test-group-addremove", asset.id)
    refetched = await group_repo.get_by_name("test-group-addremove")
    assert refetched is not None
    assert len(refetched.members) == 0


@pytest.mark.integration
async def test_asset_group_tree_top_level(db_session: AsyncSession) -> None:
    group_repo = AssetGroupRepository(db_session)
    await group_repo.create("parent-group-tree")
    child = await group_repo.create("child-group-tree")
    await group_repo.add_subgroup("parent-group-tree", child.id, weight=1.0)
    tree = await group_repo.get_tree()
    top_names = {g.name for g in tree.top_level}
    all_names = {g.name for g in tree.all_groups}
    assert "parent-group-tree" in top_names
    assert "child-group-tree" not in top_names  # it's a child, not top-level
    assert "child-group-tree" in all_names


# ---------- AssetSLOLinkRepository ----------


@pytest.mark.integration
async def test_asset_slo_link_create_list_delete(db_session: AsyncSession) -> None:
    asset_repo = AssetRepository(db_session)
    asset = await asset_repo.create("vm-link-01", type_name="vm")
    repo = AssetSLOLinkRepository(db_session)
    await repo.create(
        asset_id=asset.id,
        link_name="compilation-check",
        slo_name="linux-compilation-slo",
        sli_name="linux-compilation-sli",
        data_source_name="prometheus-dc-a",
    )
    links = await repo.list_by_asset(asset.id)
    assert len(links) == 1
    assert links[0].link_name == "compilation-check"
    await repo.delete(asset.id, "compilation-check")
    links_after = await repo.list_by_asset(asset.id)
    assert len(links_after) == 0


@pytest.mark.integration
async def test_asset_group_slo_link_crud(db_session: AsyncSession) -> None:
    group_repo = AssetGroupRepository(db_session)
    group = await group_repo.create("grp-for-slo-link")
    link_repo = AssetGroupSLOLinkRepository(db_session)
    await link_repo.create(
        group_id=group.id,
        link_name="grp-compilation-check",
        slo_name="linux-slo",
        sli_name="linux-sli",
        data_source_name="prometheus-dc-b",
    )
    links = await link_repo.list_by_group(group.id)
    assert len(links) == 1
    assert links[0].link_name == "grp-compilation-check"
    await link_repo.delete(group.id, "grp-compilation-check")
    links_after = await link_repo.list_by_group(group.id)
    assert len(links_after) == 0
