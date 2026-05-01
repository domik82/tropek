"""FastAPI router for SLO assignments and SLO group assignments."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from tropek.db.models import SLOAssignment as SLOAssignmentModel
from tropek.db.models import SLOGroupAssignment as SLOGroupAssignmentModel
from tropek.db.session import get_session
from tropek.modules.assets.comparison_rules import ComparisonRule
from tropek.modules.assets.repository import AssetGroupRepository, AssetRepository
from tropek.modules.assignments.repository import AssignmentRepository
from tropek.modules.assignments.schemas import (
    SLOAssignmentRead,
    SLOAssignmentUpgrade,
    SLOAssignmentUpsert,
    SLOGroupAssignmentRead,
    SLOGroupAssignmentUpsert,
)
from tropek.modules.common.exceptions import DomainValidationError, NotFoundError
from tropek.modules.datasource.repository import DataSourceRepository
from tropek.modules.slo_groups.repository import SLOGroupRepository
from tropek.modules.slo_registry.repository import SLORepository

router = APIRouter()


def _serialize_rules(
    rules: list[ComparisonRule] | None,
) -> list[dict[str, Any]] | None:
    """Convert typed ComparisonRule list to JSONB-ready dicts for the repository."""
    if rules is None:
        return None
    return [rule.model_dump() for rule in rules]


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
        raise NotFoundError('asset', name)
    rows = await AssignmentRepository(session).list_slo_assignments_for_asset(asset.id)
    return [_slo_assignment_read(r) for r in rows]


@router.put(
    '/assets/{name}/slo-definitions/{slo_definition_id}',
    response_model=SLOAssignmentRead,
)
async def put_asset_slo_assignment(
    name: str,
    slo_definition_id: uuid.UUID,
    body: SLOAssignmentUpsert,
    session: AsyncSession = Depends(get_session),
) -> SLOAssignmentRead:
    """Upsert an SLO assignment pinning an asset to a specific SLO definition version."""
    asset = await AssetRepository(session).get_by_name(name)
    if asset is None:
        raise NotFoundError('asset', name)

    slo_def = await SLORepository(session).get_by_id(slo_definition_id)
    if slo_def is None:
        raise NotFoundError('slo definition', str(slo_definition_id))

    datasource = await DataSourceRepository(session).get_by_name(body.data_source_name)
    if datasource is None:
        raise DomainValidationError(f"datasource '{body.data_source_name}' not found")

    row = await AssignmentRepository(session).upsert_slo_assignment(
        asset_id=asset.id,
        asset_group_id=None,
        slo_definition_id=slo_def.id,
        slo_name=slo_def.name,
        data_source_id=datasource.id,
        comparison_rules=_serialize_rules(body.comparison_rules),
    )
    row.slo_definition = slo_def
    row.data_source = datasource
    return _slo_assignment_read(row)


@router.delete(
    '/assets/{name}/slo-definitions/{slo_definition_id}',
    status_code=204,
    response_class=Response,
)
async def delete_asset_slo_assignment_by_target(
    name: str,
    slo_definition_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Remove the SLO assignment between an asset and a specific SLO definition version."""
    asset = await AssetRepository(session).get_by_name(name)
    if asset is None:
        raise NotFoundError('asset', name)
    slo_def = await SLORepository(session).get_by_id(slo_definition_id)
    if slo_def is None:
        raise NotFoundError('slo definition', str(slo_definition_id))
    await AssignmentRepository(session).delete_slo_assignment_for_target(
        asset_id=asset.id,
        asset_group_id=None,
        slo_definition_id=slo_definition_id,
    )


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
        raise NotFoundError('asset', name)
    slo_def = await SLORepository(session).get_by_id(body.new_slo_definition_id)
    if slo_def is None:
        raise DomainValidationError(f"slo definition '{body.new_slo_definition_id}' not found")
    repo = AssignmentRepository(session)
    existing = await repo.get_slo_assignment(assignment_id)
    if existing is None or existing.asset_id != asset.id:
        raise NotFoundError('assignment', str(assignment_id))
    row = await repo.upgrade_slo_assignment(assignment_id, body.new_slo_definition_id)
    if row is None:
        raise NotFoundError('assignment', str(assignment_id))
    row.slo_definition = slo_def
    data_source = await DataSourceRepository(session).get_by_id(row.data_source_id)
    assert data_source is not None  # FK constraint guarantees referent exists
    row.data_source = data_source
    return _slo_assignment_read(row)


# ---------------------------------------------------------------------------
# SLO Assignments — asset groups
# ---------------------------------------------------------------------------


@router.get('/asset-groups/{name}/slo-assignments', response_model=list[SLOAssignmentRead])
async def list_group_slo_assignments(
    name: str,
    session: AsyncSession = Depends(get_session),
) -> list[SLOAssignmentRead]:
    """List all SLO assignments for an asset group."""
    asset_group = await AssetGroupRepository(session).get_by_name(name)
    if asset_group is None:
        raise NotFoundError('asset group', name)
    rows = await AssignmentRepository(session).list_slo_assignments_for_group(asset_group.id)
    return [_slo_assignment_read(r) for r in rows]


@router.put(
    '/asset-groups/{name}/slo-definitions/{slo_definition_id}',
    response_model=SLOAssignmentRead,
)
async def put_group_slo_assignment(
    name: str,
    slo_definition_id: uuid.UUID,
    body: SLOAssignmentUpsert,
    session: AsyncSession = Depends(get_session),
) -> SLOAssignmentRead:
    """Upsert an SLO assignment pinning an asset group to a specific SLO definition version."""
    asset_group = await AssetGroupRepository(session).get_by_name(name)
    if asset_group is None:
        raise NotFoundError('asset group', name)

    slo_def = await SLORepository(session).get_by_id(slo_definition_id)
    if slo_def is None:
        raise NotFoundError('slo definition', str(slo_definition_id))

    datasource = await DataSourceRepository(session).get_by_name(body.data_source_name)
    if datasource is None:
        raise DomainValidationError(f"datasource '{body.data_source_name}' not found")

    row = await AssignmentRepository(session).upsert_slo_assignment(
        asset_id=None,
        asset_group_id=asset_group.id,
        slo_definition_id=slo_def.id,
        slo_name=slo_def.name,
        data_source_id=datasource.id,
        comparison_rules=_serialize_rules(body.comparison_rules),
    )
    row.slo_definition = slo_def
    row.data_source = datasource
    return _slo_assignment_read(row)


@router.delete(
    '/asset-groups/{name}/slo-definitions/{slo_definition_id}',
    status_code=204,
    response_class=Response,
)
async def delete_group_slo_assignment_by_target(
    name: str,
    slo_definition_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Remove the SLO assignment between an asset group and a specific SLO definition version."""
    asset_group = await AssetGroupRepository(session).get_by_name(name)
    if asset_group is None:
        raise NotFoundError('asset group', name)
    slo_def = await SLORepository(session).get_by_id(slo_definition_id)
    if slo_def is None:
        raise NotFoundError('slo definition', str(slo_definition_id))
    await AssignmentRepository(session).delete_slo_assignment_for_target(
        asset_id=None,
        asset_group_id=asset_group.id,
        slo_definition_id=slo_definition_id,
    )


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
        raise NotFoundError('asset', name)
    rows = await AssignmentRepository(session).list_group_assignments_for_asset(asset.id)
    return [_slo_group_assignment_read(r) for r in rows]


@router.put(
    '/assets/{name}/slo-groups/{slo_group_name}',
    response_model=SLOGroupAssignmentRead,
)
async def put_asset_slo_group_assignment(
    name: str,
    slo_group_name: str,
    body: SLOGroupAssignmentUpsert,
    session: AsyncSession = Depends(get_session),
) -> SLOGroupAssignmentRead:
    """Upsert an SLO group assignment pinning an asset to a specific SLO group."""
    asset = await AssetRepository(session).get_by_name(name)
    if asset is None:
        raise NotFoundError('asset', name)

    slo_group = await SLOGroupRepository(session).get_by_name(slo_group_name)
    if slo_group is None:
        raise NotFoundError('slo group', slo_group_name)

    datasource = await DataSourceRepository(session).get_by_name(body.data_source_name)
    if datasource is None:
        raise DomainValidationError(f"datasource '{body.data_source_name}' not found")

    row = await AssignmentRepository(session).upsert_group_assignment(
        asset_id=asset.id,
        asset_group_id=None,
        slo_group_id=slo_group.id,
        data_source_id=datasource.id,
    )
    row.slo_group = slo_group
    row.data_source = datasource
    return _slo_group_assignment_read(row)


@router.delete(
    '/assets/{name}/slo-groups/{slo_group_name}',
    status_code=204,
    response_class=Response,
)
async def delete_asset_slo_group_assignment_by_target(
    name: str,
    slo_group_name: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Remove the SLO group assignment between an asset and a specific SLO group."""
    asset = await AssetRepository(session).get_by_name(name)
    if asset is None:
        raise NotFoundError('asset', name)
    slo_group = await SLOGroupRepository(session).get_by_name(slo_group_name)
    if slo_group is None:
        raise NotFoundError('slo group', slo_group_name)
    await AssignmentRepository(session).delete_group_assignment_for_target(
        asset_id=asset.id,
        asset_group_id=None,
        slo_group_id=slo_group.id,
    )


# ---------------------------------------------------------------------------
# SLO Group Assignments — asset groups
# ---------------------------------------------------------------------------


@router.get('/asset-groups/{name}/slo-group-assignments', response_model=list[SLOGroupAssignmentRead])
async def list_group_group_assignments(
    name: str,
    session: AsyncSession = Depends(get_session),
) -> list[SLOGroupAssignmentRead]:
    """List all SLO group assignments for an asset group."""
    asset_group = await AssetGroupRepository(session).get_by_name(name)
    if asset_group is None:
        raise NotFoundError('asset group', name)
    rows = await AssignmentRepository(session).list_group_assignments_for_group(asset_group.id)
    return [_slo_group_assignment_read(r) for r in rows]


@router.put(
    '/asset-groups/{name}/slo-groups/{slo_group_name}',
    response_model=SLOGroupAssignmentRead,
)
async def put_group_slo_group_assignment(
    name: str,
    slo_group_name: str,
    body: SLOGroupAssignmentUpsert,
    session: AsyncSession = Depends(get_session),
) -> SLOGroupAssignmentRead:
    """Upsert an SLO group assignment pinning an asset group to a specific SLO group."""
    asset_group = await AssetGroupRepository(session).get_by_name(name)
    if asset_group is None:
        raise NotFoundError('asset group', name)

    slo_group = await SLOGroupRepository(session).get_by_name(slo_group_name)
    if slo_group is None:
        raise NotFoundError('slo group', slo_group_name)

    datasource = await DataSourceRepository(session).get_by_name(body.data_source_name)
    if datasource is None:
        raise DomainValidationError(f"datasource '{body.data_source_name}' not found")

    row = await AssignmentRepository(session).upsert_group_assignment(
        asset_id=None,
        asset_group_id=asset_group.id,
        slo_group_id=slo_group.id,
        data_source_id=datasource.id,
    )
    row.slo_group = slo_group
    row.data_source = datasource
    return _slo_group_assignment_read(row)


@router.delete(
    '/asset-groups/{name}/slo-groups/{slo_group_name}',
    status_code=204,
    response_class=Response,
)
async def delete_group_slo_group_assignment_by_target(
    name: str,
    slo_group_name: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Remove the SLO group assignment between an asset group and a specific SLO group."""
    asset_group = await AssetGroupRepository(session).get_by_name(name)
    if asset_group is None:
        raise NotFoundError('asset group', name)
    slo_group = await SLOGroupRepository(session).get_by_name(slo_group_name)
    if slo_group is None:
        raise NotFoundError('slo group', slo_group_name)
    await AssignmentRepository(session).delete_group_assignment_for_target(
        asset_id=None,
        asset_group_id=asset_group.id,
        slo_group_id=slo_group.id,
    )
