"""FastAPI router for asset types, assets, asset groups, and SLO bindings."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.assets.comparison_rules import validate_comparison_rules
from app.modules.assets.repository import (
    AssetGroupRepository,
    AssetGroupSLOLinkRepository,
    AssetRepository,
    AssetSLOLinkRepository,
    AssetTypeRepository,
    SLOBindingRepository,
)
from app.modules.assets.schemas import (
    AddMemberRequest,
    AddSubgroupRequest,
    AssetCreate,
    AssetGroupCreate,
    AssetGroupRead,
    AssetGroupSLOLinkCreate,
    AssetGroupSLOLinkRead,
    AssetGroupTreeResponse,
    AssetGroupUpdate,
    AssetRead,
    AssetSLOLinkCreate,
    AssetSLOLinkRead,
    AssetTypeCreate,
    AssetTypeRead,
    AssetTypeUpdate,
    AssetUpdate,
    ComparisonRulesUpdate,
    SLOBindingCreate,
    SLOBindingRead,
    TagKeyCount,
    TagValueCount,
)
from app.modules.common.exceptions import NotFoundError
from app.modules.common.schemas import PagedResponse
from app.modules.datasource.repository import DataSourceRepository
from app.modules.sli_registry.repository import SLIRepository
from app.modules.slo_registry.repository import SLORepository

router = APIRouter()


async def _validate_binding_adapter_type(session: AsyncSession, slo_name: str, data_source_name: str) -> None:
    """Validate datasource adapter_type matches SLO's SLI adapter_type."""
    slo_repo = SLORepository(session)
    slo_def = await slo_repo.get_latest(slo_name)
    if slo_def is None:
        raise HTTPException(status_code=422, detail=f"slo definition '{slo_name}' not found")
    ds_repo = DataSourceRepository(session)
    ds = await ds_repo.get_by_name(data_source_name)
    if ds is None:
        raise HTTPException(status_code=422, detail=f"datasource '{data_source_name}' not found")
    if slo_def.sli_name:
        sli_repo = SLIRepository(session)
        sli_def = (
            await sli_repo.get_version(slo_def.sli_name, slo_def.sli_version)
            if slo_def.sli_version
            else await sli_repo.get_latest(slo_def.sli_name)
        )
        if sli_def and sli_def.adapter_type != ds.adapter_type:
            raise HTTPException(
                status_code=422,
                detail=f"datasource adapter_type '{ds.adapter_type}' does not match sli adapter_type '{sli_def.adapter_type}'",
            )


# ---- Asset Types ----


@router.get('/asset-types', response_model=PagedResponse[AssetTypeRead])
async def list_asset_types(
    session: AsyncSession = Depends(get_session),
) -> PagedResponse[AssetTypeRead]:
    """List all asset types with asset counts."""
    repo = AssetTypeRepository(session)
    items = await repo.list_all()
    counts = await repo.get_asset_counts()
    reads = [
        AssetTypeRead(
            id=i.id,
            name=i.name,
            is_default=i.is_default,
            asset_count=counts.get(i.name, 0),
        )
        for i in items
    ]
    return PagedResponse(items=reads, total=len(reads))


@router.post('/asset-types', response_model=AssetTypeRead, status_code=201)
async def create_asset_type(
    body: AssetTypeCreate,
    session: AsyncSession = Depends(get_session),
) -> AssetTypeRead:
    """Create a new asset type."""
    repo = AssetTypeRepository(session)
    at = await repo.create(body.name, is_default=body.is_default)
    return AssetTypeRead.model_validate(at)


@router.patch('/asset-types/{name}/set-default', response_model=AssetTypeRead)
async def set_default_asset_type(
    name: str,
    session: AsyncSession = Depends(get_session),
) -> AssetTypeRead:
    """Set an asset type as the default."""
    repo = AssetTypeRepository(session)
    at = await repo.set_default(name)
    if at is None:
        raise NotFoundError('asset type', name)
    return AssetTypeRead.model_validate(at)


@router.delete('/asset-types/{name}', status_code=204)
async def delete_asset_type(
    name: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete an asset type if not in use."""
    repo = AssetTypeRepository(session)
    found = await repo.delete(name)
    if not found:
        raise NotFoundError('asset type', name)


@router.patch('/asset-types/{name}', response_model=AssetTypeRead)
async def rename_asset_type(
    name: str,
    body: AssetTypeUpdate,
    session: AsyncSession = Depends(get_session),
) -> AssetTypeRead:
    """Rename an asset type."""
    if body.name is None:
        raise HTTPException(status_code=422, detail='name is required')
    repo = AssetTypeRepository(session)
    at = await repo.rename(name, body.name)
    if at is None:
        raise NotFoundError('asset type', name)
    return AssetTypeRead.model_validate(at)


# ---- Assets ----


@router.get('/assets', response_model=PagedResponse[AssetRead])
async def list_assets(
    type_name: str | None = None,
    tag_key: str | None = None,
    tag_val: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> PagedResponse[AssetRead]:
    """List all assets with optional type or tag filters."""
    repo = AssetRepository(session)
    items = await repo.list_all(type_name=type_name, tag_key=tag_key, tag_val=tag_val)
    return PagedResponse(items=[AssetRead.model_validate(a) for a in items], total=len(items))


@router.post('/assets', response_model=AssetRead, status_code=201)
async def create_asset(
    body: AssetCreate,
    session: AsyncSession = Depends(get_session),
) -> AssetRead:
    """Create a new asset."""
    repo = AssetRepository(session)
    asset = await repo.create(
        body.name,
        type_name=body.type_name,
        display_name=body.display_name,
        color=body.color,
        tags=body.tags,
        variables=body.variables,
    )
    return AssetRead.model_validate(asset)


@router.get('/assets/tag-keys', response_model=list[TagKeyCount])
async def list_tag_keys(
    session: AsyncSession = Depends(get_session),
) -> list[TagKeyCount]:
    """List all distinct tag keys with usage counts."""
    repo = AssetRepository(session)
    keys = await repo.get_tag_keys()
    return [TagKeyCount(key=k, count=v) for k, v in keys.items()]


@router.get('/assets/tag-values', response_model=list[TagValueCount])
async def list_tag_values(
    key: str,
    session: AsyncSession = Depends(get_session),
) -> list[TagValueCount]:
    """List all distinct values for a tag key with usage counts."""
    repo = AssetRepository(session)
    values = await repo.get_tag_values(key)
    return [TagValueCount(value=k, count=v) for k, v in values.items()]


@router.get('/assets/{name}', response_model=AssetRead)
async def get_asset(
    name: str,
    session: AsyncSession = Depends(get_session),
) -> AssetRead:
    """Get an asset by name."""
    repo = AssetRepository(session)
    asset = await repo.get_by_name(name)
    if asset is None:
        raise NotFoundError('asset', name)
    return AssetRead.model_validate(asset)


@router.patch('/assets/{name}', response_model=AssetRead)
async def update_asset(
    name: str,
    body: AssetUpdate,
    session: AsyncSession = Depends(get_session),
) -> AssetRead:
    """Update mutable asset fields."""
    repo = AssetRepository(session)
    asset = await repo.update(name, **body.model_dump(exclude_none=True))
    return AssetRead.model_validate(asset)


@router.delete('/assets/{name}', status_code=204)
async def delete_asset(
    name: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete an asset and all its group memberships and SLO links."""
    repo = AssetRepository(session)
    found = await repo.delete(name)
    if not found:
        raise NotFoundError('asset', name)


# ---- Asset SLO Links ----


@router.get('/assets/{name}/slo-links', response_model=list[AssetSLOLinkRead])
async def list_asset_slo_links(
    name: str,
    session: AsyncSession = Depends(get_session),
) -> list[AssetSLOLinkRead]:
    """List all SLO links for an asset."""
    asset_repo = AssetRepository(session)
    asset = await asset_repo.get_by_name(name)
    if asset is None:
        raise NotFoundError('asset', name)
    link_repo = AssetSLOLinkRepository(session)
    links = await link_repo.list_by_asset(asset.id)
    return [AssetSLOLinkRead.model_validate(lnk) for lnk in links]


@router.post('/assets/{name}/slo-links', response_model=AssetSLOLinkRead, status_code=201)
async def create_asset_slo_link(
    name: str,
    body: AssetSLOLinkCreate,
    session: AsyncSession = Depends(get_session),
) -> AssetSLOLinkRead:
    """Create an SLO link for an asset."""
    asset_repo = AssetRepository(session)
    asset = await asset_repo.get_by_name(name)
    if asset is None:
        raise NotFoundError('asset', name)
    link_repo = AssetSLOLinkRepository(session)
    link = await link_repo.create(
        asset_id=asset.id,
        link_name=body.link_name,
        slo_name=body.slo_name,
        sli_name=body.sli_name,
        data_source_name=body.data_source_name,
    )
    return AssetSLOLinkRead.model_validate(link)


@router.delete('/assets/{name}/slo-links/{link_name}', status_code=204)
async def delete_asset_slo_link(
    name: str,
    link_name: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete an SLO link from an asset."""
    asset_repo = AssetRepository(session)
    asset = await asset_repo.get_by_name(name)
    if asset is None:
        raise NotFoundError('asset', name)
    link_repo = AssetSLOLinkRepository(session)
    await link_repo.delete(asset.id, link_name)


@router.get(
    '/assets/{name}/slo-links/{link_name}/comparison-rules',
    response_model=list[dict[str, Any]],
)
async def get_comparison_rules(
    name: str,
    link_name: str,
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """Return comparison rules for an asset SLO link."""
    asset_repo = AssetRepository(session)
    asset = await asset_repo.get_by_name(name)
    if asset is None:
        raise NotFoundError('asset', name)
    link_repo = AssetSLOLinkRepository(session)
    link = await link_repo.get_by_link_name(asset.id, link_name)
    if link is None:
        raise NotFoundError('slo link', link_name)
    return link.comparison_rules


@router.put(
    '/assets/{name}/slo-links/{link_name}/comparison-rules',
    response_model=list[dict[str, Any]],
)
async def update_comparison_rules_endpoint(
    name: str,
    link_name: str,
    body: ComparisonRulesUpdate,
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """Replace comparison rules for an asset SLO link.

    Validates rule structure:
    - At most one catch-all rule (match: {})
    - Catch-all must be last
    - match must be dict[str, str]
    - compare_to must be dict[str, str | bool]
    """
    asset_repo = AssetRepository(session)
    asset = await asset_repo.get_by_name(name)
    if asset is None:
        raise NotFoundError('asset', name)
    link_repo = AssetSLOLinkRepository(session)
    link = await link_repo.get_by_link_name(asset.id, link_name)
    if link is None:
        raise NotFoundError('slo link', link_name)
    try:
        validated = validate_comparison_rules(body.rules)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    rules_dicts = [r.model_dump() for r in validated]
    await link_repo.update_comparison_rules(link.id, rules_dicts)
    return rules_dicts


# ---- Asset Groups ----
# NOTE: /asset-groups/tree MUST be registered before /asset-groups/{name}


@router.get('/asset-groups', response_model=PagedResponse[AssetGroupRead])
async def list_asset_groups(
    session: AsyncSession = Depends(get_session),
) -> PagedResponse[AssetGroupRead]:
    """List all asset groups."""
    repo = AssetGroupRepository(session)
    items = await repo.list_all()
    return PagedResponse(items=items, total=len(items))


@router.get('/asset-groups/tree', response_model=AssetGroupTreeResponse)
async def get_asset_group_tree(
    session: AsyncSession = Depends(get_session),
) -> AssetGroupTreeResponse:
    """Get the full asset group hierarchy tree."""
    repo = AssetGroupRepository(session)
    return await repo.get_tree()


@router.post('/asset-groups', response_model=AssetGroupRead, status_code=201)
async def create_asset_group(
    body: AssetGroupCreate,
    session: AsyncSession = Depends(get_session),
) -> AssetGroupRead:
    """Create a new asset group."""
    repo = AssetGroupRepository(session)
    return await repo.create(
        body.name,
        display_name=body.display_name,
        description=body.description,
        color=body.color,
        members=body.members,
        subgroups=body.subgroups,
    )


@router.get('/asset-groups/{name}', response_model=AssetGroupRead)
async def get_asset_group(
    name: str,
    session: AsyncSession = Depends(get_session),
) -> AssetGroupRead:
    """Get an asset group by name."""
    repo = AssetGroupRepository(session)
    group = await repo.get_by_name(name)
    if group is None:
        raise NotFoundError('asset group', name)
    return group


@router.patch('/asset-groups/{name}', response_model=AssetGroupRead)
async def update_asset_group(
    name: str,
    body: AssetGroupUpdate,
    session: AsyncSession = Depends(get_session),
) -> AssetGroupRead:
    """Update mutable asset group fields."""
    repo = AssetGroupRepository(session)
    group = await repo.update(name, **body.model_dump(exclude_none=True))
    if group is None:
        raise NotFoundError('asset group', name)
    return group


@router.delete('/asset-groups/{name}', status_code=204)
async def delete_asset_group(
    name: str,
    deactivate_slos: bool = False,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete an asset group and optionally deactivate linked SLOs."""
    repo = AssetGroupRepository(session)
    found = await repo.delete_group(name, deactivate_slos=deactivate_slos)
    if not found:
        raise NotFoundError('asset group', name)


@router.post('/asset-groups/{name}/members', response_model=AssetGroupRead, status_code=201)
async def add_group_member(
    name: str,
    body: AddMemberRequest,
    session: AsyncSession = Depends(get_session),
) -> AssetGroupRead:
    """Add a member asset to a group."""
    repo = AssetGroupRepository(session)
    group = await repo.get_by_name(name)
    if group is None:
        raise NotFoundError('asset group', name)
    return await repo.add_member(name, body.asset_id, weight=body.weight)


@router.delete('/asset-groups/{name}/members/{asset_id}', status_code=204)
async def remove_group_member(
    name: str,
    asset_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Remove a member asset from a group."""
    repo = AssetGroupRepository(session)
    group = await repo.get_by_name(name)
    if group is None:
        raise NotFoundError('asset group', name)
    await repo.remove_member(name, asset_id)


@router.post('/asset-groups/{name}/subgroups', response_model=AssetGroupRead, status_code=201)
async def add_group_subgroup(
    name: str,
    body: AddSubgroupRequest,
    session: AsyncSession = Depends(get_session),
) -> AssetGroupRead:
    """Add a child subgroup to a group."""
    repo = AssetGroupRepository(session)
    group = await repo.get_by_name(name)
    if group is None:
        raise NotFoundError('asset group', name)
    return await repo.add_subgroup(name, body.child_group_id, weight=body.weight)


@router.delete('/asset-groups/{name}/subgroups/{child_group_id}', status_code=204)
async def remove_group_subgroup(
    name: str,
    child_group_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Remove a child subgroup from a group."""
    repo = AssetGroupRepository(session)
    group = await repo.get_by_name(name)
    if group is None:
        raise NotFoundError('asset group', name)
    await repo.remove_subgroup(name, child_group_id)


# ---- Asset Group SLO Links ----


@router.get('/asset-groups/{name}/slo-links', response_model=list[AssetGroupSLOLinkRead])
async def list_group_slo_links(
    name: str,
    session: AsyncSession = Depends(get_session),
) -> list[AssetGroupSLOLinkRead]:
    """List all SLO links for an asset group."""
    group_repo = AssetGroupRepository(session)
    group = await group_repo.get_by_name(name)
    if group is None:
        raise NotFoundError('asset group', name)
    link_repo = AssetGroupSLOLinkRepository(session)
    links = await link_repo.list_by_group(group.id)
    return [AssetGroupSLOLinkRead.model_validate(lnk) for lnk in links]


@router.post('/asset-groups/{name}/slo-links', response_model=AssetGroupSLOLinkRead, status_code=201)
async def create_group_slo_link(
    name: str,
    body: AssetGroupSLOLinkCreate,
    session: AsyncSession = Depends(get_session),
) -> AssetGroupSLOLinkRead:
    """Create an SLO link for an asset group."""
    group_repo = AssetGroupRepository(session)
    group = await group_repo.get_by_name(name)
    if group is None:
        raise NotFoundError('asset group', name)
    link_repo = AssetGroupSLOLinkRepository(session)
    link = await link_repo.create(
        group_id=group.id,
        slo_name=body.slo_name,
        sli_name=body.sli_name,
        data_source_name=body.data_source_name,
    )
    return AssetGroupSLOLinkRead.model_validate(link)


@router.delete('/asset-groups/{name}/slo-links/{link_name}', status_code=204)
async def delete_group_slo_link(
    name: str,
    link_name: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete an SLO link from an asset group."""
    group_repo = AssetGroupRepository(session)
    group = await group_repo.get_by_name(name)
    if group is None:
        raise NotFoundError('asset group', name)
    link_repo = AssetGroupSLOLinkRepository(session)
    await link_repo.delete(group.id, link_name)


# ---- SLO Bindings (new model) ----


@router.get('/assets/{name}/slo-bindings', response_model=list[SLOBindingRead])
async def list_asset_slo_bindings(
    name: str,
    session: AsyncSession = Depends(get_session),
) -> list[SLOBindingRead]:
    """List all SLO bindings for an asset."""
    asset_repo = AssetRepository(session)
    asset = await asset_repo.get_by_name(name)
    if asset is None:
        raise NotFoundError('asset', name)
    binding_repo = SLOBindingRepository(session)
    bindings = await binding_repo.list_by_target('asset', asset.id)
    return [SLOBindingRead.model_validate(b) for b in bindings]


@router.post('/assets/{name}/slo-bindings', response_model=SLOBindingRead, status_code=201)
async def create_asset_slo_binding(
    name: str,
    body: SLOBindingCreate,
    session: AsyncSession = Depends(get_session),
) -> SLOBindingRead:
    """Create an SLO binding for an asset."""
    asset_repo = AssetRepository(session)
    asset = await asset_repo.get_by_name(name)
    if asset is None:
        raise NotFoundError('asset', name)
    await _validate_binding_adapter_type(session, body.slo_name, body.data_source_name)
    binding_repo = SLOBindingRepository(session)
    binding = await binding_repo.create(
        target_type='asset',
        target_id=asset.id,
        slo_name=body.slo_name,
        data_source_name=body.data_source_name,
    )
    return SLOBindingRead.model_validate(binding)


@router.delete('/assets/{name}/slo-bindings/{slo_name}', status_code=204)
async def delete_asset_slo_binding(
    name: str,
    slo_name: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete an SLO binding from an asset."""
    asset_repo = AssetRepository(session)
    asset = await asset_repo.get_by_name(name)
    if asset is None:
        raise NotFoundError('asset', name)
    binding_repo = SLOBindingRepository(session)
    await binding_repo.delete_by_target_and_slo('asset', asset.id, slo_name)


@router.get(
    '/assets/{name}/slo-bindings/{slo_name}/comparison-rules',
    response_model=list[dict[str, Any]],
)
async def get_binding_comparison_rules(
    name: str,
    slo_name: str,
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """Return comparison rules for an asset SLO binding."""
    asset_repo = AssetRepository(session)
    asset = await asset_repo.get_by_name(name)
    if asset is None:
        raise NotFoundError('asset', name)
    binding_repo = SLOBindingRepository(session)
    binding = await binding_repo.find_for_asset(asset.id, slo_name)
    if binding is None:
        raise NotFoundError('slo binding', slo_name)
    return binding.comparison_rules or []


@router.put(
    '/assets/{name}/slo-bindings/{slo_name}/comparison-rules',
    response_model=list[dict[str, Any]],
)
async def update_binding_comparison_rules(
    name: str,
    slo_name: str,
    body: ComparisonRulesUpdate,
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """Replace comparison rules for an asset SLO binding.

    Validates rule structure: each rule must have 'match' and 'compare_to' dicts.
    """
    asset_repo = AssetRepository(session)
    asset = await asset_repo.get_by_name(name)
    if asset is None:
        raise NotFoundError('asset', name)
    binding_repo = SLOBindingRepository(session)
    binding = await binding_repo.find_for_asset(asset.id, slo_name)
    if binding is None:
        raise NotFoundError('slo binding', slo_name)
    try:
        validated = validate_comparison_rules(body.rules)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    rules_dicts = [r.model_dump() for r in validated]
    await binding_repo.update_comparison_rules('asset', asset.id, slo_name, rules_dicts)
    await session.commit()
    return rules_dicts


@router.get('/asset-groups/{name}/slo-bindings', response_model=list[SLOBindingRead])
async def list_group_slo_bindings(
    name: str,
    session: AsyncSession = Depends(get_session),
) -> list[SLOBindingRead]:
    """List all SLO bindings for an asset group."""
    group_repo = AssetGroupRepository(session)
    group = await group_repo.get_by_name(name)
    if group is None:
        raise NotFoundError('asset group', name)
    binding_repo = SLOBindingRepository(session)
    bindings = await binding_repo.list_by_target('asset_group', group.id)
    return [SLOBindingRead.model_validate(b) for b in bindings]


@router.post('/asset-groups/{name}/slo-bindings', response_model=SLOBindingRead, status_code=201)
async def create_group_slo_binding(
    name: str,
    body: SLOBindingCreate,
    session: AsyncSession = Depends(get_session),
) -> SLOBindingRead:
    """Create an SLO binding for an asset group."""
    group_repo = AssetGroupRepository(session)
    group = await group_repo.get_by_name(name)
    if group is None:
        raise NotFoundError('asset group', name)
    await _validate_binding_adapter_type(session, body.slo_name, body.data_source_name)
    binding_repo = SLOBindingRepository(session)
    binding = await binding_repo.create(
        target_type='asset_group',
        target_id=group.id,
        slo_name=body.slo_name,
        data_source_name=body.data_source_name,
    )
    return SLOBindingRead.model_validate(binding)


@router.delete('/asset-groups/{name}/slo-bindings/{slo_name}', status_code=204)
async def delete_group_slo_binding(
    name: str,
    slo_name: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete an SLO binding from an asset group."""
    group_repo = AssetGroupRepository(session)
    group = await group_repo.get_by_name(name)
    if group is None:
        raise NotFoundError('asset group', name)
    binding_repo = SLOBindingRepository(session)
    await binding_repo.delete_by_target_and_slo('asset_group', group.id, slo_name)
