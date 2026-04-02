"""FastAPI router for SLO display groups."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.common.errors import raise_not_found
from app.modules.display_groups.repository import DisplayGroupRepository
from app.modules.display_groups.schemas import (
    DisplayGroupCreate,
    DisplayGroupMemberAdd,
    DisplayGroupRead,
)

router = APIRouter()


@router.get('/slo-display-groups', response_model=list[DisplayGroupRead])
async def list_display_groups(
    session: AsyncSession = Depends(get_session),
) -> list[DisplayGroupRead]:
    """List all SLO display groups."""
    groups = await DisplayGroupRepository(session).list_all()
    return [DisplayGroupRead.model_validate(g) for g in groups]


@router.post('/slo-display-groups', response_model=DisplayGroupRead, status_code=201)
async def create_display_group(
    body: DisplayGroupCreate,
    session: AsyncSession = Depends(get_session),
) -> DisplayGroupRead:
    """Create a new SLO display group."""
    group = await DisplayGroupRepository(session).create(
        name=body.name,
        display_name=body.display_name,
        parent_id=body.parent_id,
        sort_order=body.sort_order,
    )
    return DisplayGroupRead.model_validate(group)


@router.delete('/slo-display-groups/{name}', status_code=204)
async def delete_display_group(
    name: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete a display group and all its memberships."""
    repo = DisplayGroupRepository(session)
    if await repo.get_by_name(name) is None:
        raise_not_found('slo display group', name)
    await repo.delete(name)


@router.get('/slo-display-groups/{name}/members', response_model=list[str])
async def list_members(name: str, session: AsyncSession = Depends(get_session)) -> list[str]:
    """List SLO concept names in this display group."""
    repo = DisplayGroupRepository(session)
    group = await repo.get_by_name(name)
    if group is None:
        raise_not_found('slo display group', name)
    return await repo.list_members(group.id)


@router.post('/slo-display-groups/{name}/members', status_code=204)
async def add_member(
    name: str,
    body: DisplayGroupMemberAdd,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Add an SLO concept to this display group."""
    repo = DisplayGroupRepository(session)
    group = await repo.get_by_name(name)
    if group is None:
        raise_not_found('slo display group', name)
    await repo.add_member(group.id, body.slo_name)


@router.delete('/slo-display-groups/{name}/members/{slo_name}', status_code=204)
async def remove_member(
    name: str,
    slo_name: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Remove an SLO concept from this display group."""
    repo = DisplayGroupRepository(session)
    group = await repo.get_by_name(name)
    if group is None:
        raise_not_found('slo display group', name)
    await repo.remove_member(group.id, slo_name)
