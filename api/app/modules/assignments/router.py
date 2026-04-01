"""FastAPI router for SLO assignments and SLO group assignments."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.assets.repository import AssetGroupRepository, AssetRepository
from app.modules.assignments.repository import AssignmentRepository
from app.modules.assignments.schemas import (
    SLOAssignmentCreate,
    SLOAssignmentRead,
    SLOAssignmentUpgrade,
    SLOGroupAssignmentCreate,
    SLOGroupAssignmentRead,
)
from app.modules.common.errors import raise_not_found
from app.modules.datasource.repository import DataSourceRepository
from app.modules.slo_groups.repository import SLOGroupRepository
from app.modules.slo_registry.repository import SLORepository

router = APIRouter()


# ---------------------------------------------------------------------------
# SLO Assignments — assets
# ---------------------------------------------------------------------------


@router.get('/assets/{name}/slo-assignments', response_model=list[SLOAssignmentRead])
async def list_asset_slo_assignments(
    name: str,
    session: AsyncSession = Depends(get_session),
) -> list[SLOAssignmentRead]:
    """List all SLO assignments for an asset."""
    asset = await AssetRepository(session).get_by_name(name)
    if asset is None:
        raise_not_found('asset', name)
    rows = await AssignmentRepository(session).list_slo_assignments_for_asset(asset.id)
    return [SLOAssignmentRead.model_validate(r) for r in rows]


@router.post('/assets/{name}/slo-assignments', response_model=SLOAssignmentRead, status_code=201)
async def create_asset_slo_assignment(
    name: str,
    body: SLOAssignmentCreate,
    session: AsyncSession = Depends(get_session),
) -> SLOAssignmentRead:
    """Assign a specific SLO definition version to an asset."""
    asset = await AssetRepository(session).get_by_name(name)
    if asset is None:
        raise_not_found('asset', name)

    slo_def = await SLORepository(session).get_by_id(body.slo_definition_id)
    if slo_def is None:
        raise HTTPException(
            status_code=422, detail=f"slo definition '{body.slo_definition_id}' not found"
        )

    ds = await DataSourceRepository(session).get_by_name(body.data_source_name)
    if ds is None:
        raise HTTPException(
            status_code=422, detail=f"datasource '{body.data_source_name}' not found"
        )

    try:
        row = await AssignmentRepository(session).create_slo_assignment(
            asset_id=asset.id,
            asset_group_id=None,
            slo_definition_id=slo_def.id,
            slo_name=slo_def.name,
            data_source_id=ds.id,
            comparison_rules=body.comparison_rules,
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail='slo assignment already exists for this asset and slo name',
        ) from exc
    return SLOAssignmentRead.model_validate(row)


@router.patch(
    '/assets/{name}/slo-assignments/{assignment_id}',
    response_model=SLOAssignmentRead,
)
async def upgrade_asset_slo_assignment(
    name: str,
    assignment_id: uuid.UUID,
    body: SLOAssignmentUpgrade,
    session: AsyncSession = Depends(get_session),
) -> SLOAssignmentRead:
    """Upgrade an SLO assignment to a new definition version."""
    row = await AssignmentRepository(session).upgrade_slo_assignment(
        assignment_id, body.new_slo_definition_id
    )
    if row is None:
        raise HTTPException(status_code=404, detail='assignment not found')
    return SLOAssignmentRead.model_validate(row)


@router.delete('/assets/{name}/slo-assignments/{assignment_id}', status_code=204)
async def delete_asset_slo_assignment(
    name: str,
    assignment_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Remove an SLO assignment from an asset."""
    await AssignmentRepository(session).delete_slo_assignment(assignment_id)


# ---------------------------------------------------------------------------
# SLO Assignments — asset groups
# ---------------------------------------------------------------------------


@router.get('/asset-groups/{name}/slo-assignments', response_model=list[SLOAssignmentRead])
async def list_group_slo_assignments(
    name: str,
    session: AsyncSession = Depends(get_session),
) -> list[SLOAssignmentRead]:
    """List all SLO assignments for an asset group."""
    ag = await AssetGroupRepository(session).get_by_name(name)
    if ag is None:
        raise_not_found('asset group', name)
    rows = await AssignmentRepository(session).list_slo_assignments_for_group(ag.id)
    return [SLOAssignmentRead.model_validate(r) for r in rows]


@router.post(
    '/asset-groups/{name}/slo-assignments', response_model=SLOAssignmentRead, status_code=201
)
async def create_group_slo_assignment(
    name: str,
    body: SLOAssignmentCreate,
    session: AsyncSession = Depends(get_session),
) -> SLOAssignmentRead:
    """Assign a specific SLO definition version to an asset group."""
    ag = await AssetGroupRepository(session).get_by_name(name)
    if ag is None:
        raise_not_found('asset group', name)

    slo_def = await SLORepository(session).get_by_id(body.slo_definition_id)
    if slo_def is None:
        raise HTTPException(
            status_code=422, detail=f"slo definition '{body.slo_definition_id}' not found"
        )

    ds = await DataSourceRepository(session).get_by_name(body.data_source_name)
    if ds is None:
        raise HTTPException(
            status_code=422, detail=f"datasource '{body.data_source_name}' not found"
        )

    try:
        row = await AssignmentRepository(session).create_slo_assignment(
            asset_id=None,
            asset_group_id=ag.id,
            slo_definition_id=slo_def.id,
            slo_name=slo_def.name,
            data_source_id=ds.id,
            comparison_rules=body.comparison_rules,
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail='slo assignment already exists for this group and slo name',
        ) from exc
    return SLOAssignmentRead.model_validate(row)


@router.delete('/asset-groups/{name}/slo-assignments/{assignment_id}', status_code=204)
async def delete_group_slo_assignment(
    name: str,
    assignment_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Remove an SLO assignment from an asset group."""
    await AssignmentRepository(session).delete_slo_assignment(assignment_id)


# ---------------------------------------------------------------------------
# SLO Group Assignments — assets
# ---------------------------------------------------------------------------


@router.get('/assets/{name}/slo-group-assignments', response_model=list[SLOGroupAssignmentRead])
async def list_asset_group_assignments(
    name: str,
    session: AsyncSession = Depends(get_session),
) -> list[SLOGroupAssignmentRead]:
    """List all SLO group assignments for an asset."""
    asset = await AssetRepository(session).get_by_name(name)
    if asset is None:
        raise_not_found('asset', name)
    rows = await AssignmentRepository(session).list_group_assignments_for_asset(asset.id)
    return [SLOGroupAssignmentRead.model_validate(r) for r in rows]


@router.post(
    '/assets/{name}/slo-group-assignments',
    response_model=SLOGroupAssignmentRead,
    status_code=201,
)
async def create_asset_group_assignment(
    name: str,
    body: SLOGroupAssignmentCreate,
    session: AsyncSession = Depends(get_session),
) -> SLOGroupAssignmentRead:
    """Assign an SLO group to an asset (always-latest semantics)."""
    asset = await AssetRepository(session).get_by_name(name)
    if asset is None:
        raise_not_found('asset', name)

    sg = await SLOGroupRepository(session).get_by_name(body.slo_group_name)
    if sg is None:
        raise HTTPException(
            status_code=422, detail=f"slo group '{body.slo_group_name}' not found"
        )

    ds = await DataSourceRepository(session).get_by_name(body.data_source_name)
    if ds is None:
        raise HTTPException(
            status_code=422, detail=f"datasource '{body.data_source_name}' not found"
        )

    try:
        row = await AssignmentRepository(session).create_group_assignment(
            asset_id=asset.id,
            asset_group_id=None,
            slo_group_id=sg.id,
            data_source_id=ds.id,
        )
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail='group assignment already exists') from exc
    return SLOGroupAssignmentRead.model_validate(row)


@router.delete('/assets/{name}/slo-group-assignments/{assignment_id}', status_code=204)
async def delete_asset_group_assignment(
    name: str,
    assignment_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Remove an SLO group assignment from an asset."""
    await AssignmentRepository(session).delete_group_assignment(assignment_id)


# ---------------------------------------------------------------------------
# SLO Group Assignments — asset groups
# ---------------------------------------------------------------------------


@router.get(
    '/asset-groups/{name}/slo-group-assignments', response_model=list[SLOGroupAssignmentRead]
)
async def list_group_group_assignments(
    name: str,
    session: AsyncSession = Depends(get_session),
) -> list[SLOGroupAssignmentRead]:
    """List all SLO group assignments for an asset group."""
    ag = await AssetGroupRepository(session).get_by_name(name)
    if ag is None:
        raise_not_found('asset group', name)
    rows = await AssignmentRepository(session).list_group_assignments_for_group(ag.id)
    return [SLOGroupAssignmentRead.model_validate(r) for r in rows]


@router.post(
    '/asset-groups/{name}/slo-group-assignments',
    response_model=SLOGroupAssignmentRead,
    status_code=201,
)
async def create_group_group_assignment(
    name: str,
    body: SLOGroupAssignmentCreate,
    session: AsyncSession = Depends(get_session),
) -> SLOGroupAssignmentRead:
    """Assign an SLO group to an asset group (always-latest semantics)."""
    ag = await AssetGroupRepository(session).get_by_name(name)
    if ag is None:
        raise_not_found('asset group', name)

    sg = await SLOGroupRepository(session).get_by_name(body.slo_group_name)
    if sg is None:
        raise HTTPException(
            status_code=422, detail=f"slo group '{body.slo_group_name}' not found"
        )

    ds = await DataSourceRepository(session).get_by_name(body.data_source_name)
    if ds is None:
        raise HTTPException(
            status_code=422, detail=f"datasource '{body.data_source_name}' not found"
        )

    try:
        row = await AssignmentRepository(session).create_group_assignment(
            asset_id=None,
            asset_group_id=ag.id,
            slo_group_id=sg.id,
            data_source_id=ds.id,
        )
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail='group assignment already exists') from exc
    return SLOGroupAssignmentRead.model_validate(row)


@router.delete('/asset-groups/{name}/slo-group-assignments/{assignment_id}', status_code=204)
async def delete_group_group_assignment(
    name: str,
    assignment_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Remove an SLO group assignment from an asset group."""
    await AssignmentRepository(session).delete_group_assignment(assignment_id)
