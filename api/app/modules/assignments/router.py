"""FastAPI router for SLO assignments and SLO group assignments."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SLOAssignment as SLOAssignmentModel
from app.db.models import SLOGroupAssignment as SLOGroupAssignmentModel
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


def _slo_assignment_read(row: SLOAssignmentModel) -> SLOAssignmentRead:
    """Build enriched SLOAssignmentRead from ORM row with eager-loaded relations."""
    return SLOAssignmentRead(
        id=row.id,
        asset_id=row.asset_id,
        asset_group_id=row.asset_group_id,
        slo_definition_id=row.slo_definition_id,
        slo_name=row.slo_name,
        slo_version=row.slo_definition.version,
        data_source_id=row.data_source_id,
        data_source_name=row.data_source.name,
        comparison_rules=row.comparison_rules,
        created_at=row.created_at,
    )


def _slo_group_assignment_read(row: SLOGroupAssignmentModel) -> SLOGroupAssignmentRead:
    """Build enriched SLOGroupAssignmentRead from ORM row with eager-loaded relations."""
    return SLOGroupAssignmentRead(
        id=row.id,
        asset_id=row.asset_id,
        asset_group_id=row.asset_group_id,
        slo_group_id=row.slo_group_id,
        slo_group_name=row.slo_group.name,
        data_source_id=row.data_source_id,
        data_source_name=row.data_source.name,
        created_at=row.created_at,
    )


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
    return [_slo_assignment_read(r) for r in rows]


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
    # Attach loaded relations for enriched response
    row.slo_definition = slo_def
    row.data_source = ds
    return _slo_assignment_read(row)


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
    asset = await AssetRepository(session).get_by_name(name)
    if asset is None:
        raise_not_found('asset', name)
    slo_def = await SLORepository(session).get_by_id(body.new_slo_definition_id)
    if slo_def is None:
        raise HTTPException(
            status_code=422, detail=f"slo definition '{body.new_slo_definition_id}' not found"
        )
    repo = AssignmentRepository(session)
    existing = await repo.get_slo_assignment(assignment_id)
    if existing is None or existing.asset_id != asset.id:
        raise HTTPException(status_code=404, detail='assignment not found')
    row = await repo.upgrade_slo_assignment(assignment_id, body.new_slo_definition_id)
    if row is None:
        raise HTTPException(status_code=404, detail='assignment not found')
    row.slo_definition = slo_def
    row.data_source = existing.data_source if hasattr(existing, 'data_source') else await DataSourceRepository(session).get_by_id(row.data_source_id)
    return _slo_assignment_read(row)


@router.delete('/assets/{name}/slo-assignments/{assignment_id}', status_code=204)
async def delete_asset_slo_assignment(
    name: str,
    assignment_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Remove an SLO assignment from an asset."""
    asset = await AssetRepository(session).get_by_name(name)
    if asset is None:
        raise_not_found('asset', name)
    repo = AssignmentRepository(session)
    row = await repo.get_slo_assignment(assignment_id)
    if row is None or row.asset_id != asset.id:
        raise HTTPException(status_code=404, detail='assignment not found')
    await repo.delete_slo_assignment(assignment_id)


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
    return [_slo_assignment_read(r) for r in rows]


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
    row.slo_definition = slo_def
    row.data_source = ds
    return _slo_assignment_read(row)


@router.delete('/asset-groups/{name}/slo-assignments/{assignment_id}', status_code=204)
async def delete_group_slo_assignment(
    name: str,
    assignment_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Remove an SLO assignment from an asset group."""
    ag = await AssetGroupRepository(session).get_by_name(name)
    if ag is None:
        raise_not_found('asset group', name)
    repo = AssignmentRepository(session)
    row = await repo.get_slo_assignment(assignment_id)
    if row is None or row.asset_group_id != ag.id:
        raise HTTPException(status_code=404, detail='assignment not found')
    await repo.delete_slo_assignment(assignment_id)


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
    return [_slo_group_assignment_read(r) for r in rows]


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
    row.slo_group = sg
    row.data_source = ds
    return _slo_group_assignment_read(row)


@router.delete('/assets/{name}/slo-group-assignments/{assignment_id}', status_code=204)
async def delete_asset_group_assignment(
    name: str,
    assignment_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Remove an SLO group assignment from an asset."""
    asset = await AssetRepository(session).get_by_name(name)
    if asset is None:
        raise_not_found('asset', name)
    repo = AssignmentRepository(session)
    row = await repo.get_group_assignment(assignment_id)
    if row is None or row.asset_id != asset.id:
        raise HTTPException(status_code=404, detail='assignment not found')
    await repo.delete_group_assignment(assignment_id)


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
    return [_slo_group_assignment_read(r) for r in rows]


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
    row.slo_group = sg
    row.data_source = ds
    return _slo_group_assignment_read(row)


@router.delete('/asset-groups/{name}/slo-group-assignments/{assignment_id}', status_code=204)
async def delete_group_group_assignment(
    name: str,
    assignment_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Remove an SLO group assignment from an asset group."""
    ag = await AssetGroupRepository(session).get_by_name(name)
    if ag is None:
        raise_not_found('asset group', name)
    repo = AssignmentRepository(session)
    row = await repo.get_group_assignment(assignment_id)
    if row is None or row.asset_group_id != ag.id:
        raise HTTPException(status_code=404, detail='assignment not found')
    await repo.delete_group_assignment(assignment_id)
