"""FastAPI router for SLO definition versioned CRUD."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.common.errors import raise_not_found
from app.modules.common.schemas import PagedResponse
from app.modules.slo_registry.repository import SLORepository
from app.modules.slo_registry.schemas import SLODefinitionCreate, SLODefinitionRead

router = APIRouter()


@router.get("/slo-definitions", response_model=PagedResponse[SLODefinitionRead])
async def list_slo_definitions(
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> PagedResponse[SLODefinitionRead]:
    """List all active SLO definitions."""
    repo = SLORepository(session)
    items = await repo.list_all()
    return PagedResponse(
        items=[SLODefinitionRead.model_validate(i) for i in items], total=len(items)
    )


@router.post("/slo-definitions", response_model=SLODefinitionRead, status_code=201)
async def create_slo_definition(
    body: SLODefinitionCreate,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> SLODefinitionRead:
    """Create a new SLO definition (or a new version if name already exists)."""
    repo = SLORepository(session)
    slo = await repo.create(
        body.name,
        slo_yaml=body.slo_yaml,
        display_name=body.display_name,
        notes=body.notes,
        author=body.author,
        meta=body.meta,
    )
    return SLODefinitionRead.model_validate(slo)


@router.get("/slo-definitions/{name}", response_model=SLODefinitionRead)
async def get_slo_definition(
    name: str,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> SLODefinitionRead:
    """Get the latest active version of an SLO definition."""
    repo = SLORepository(session)
    slo = await repo.get_latest(name)
    if slo is None:
        raise_not_found("slo definition", name)
    return SLODefinitionRead.model_validate(slo)


@router.get("/slo-definitions/{name}/versions", response_model=list[SLODefinitionRead])
async def list_slo_versions(
    name: str,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> list[SLODefinitionRead]:
    """List all versions of an SLO definition."""
    repo = SLORepository(session)
    versions = await repo.list_versions(name)
    return [SLODefinitionRead.model_validate(v) for v in versions]


@router.delete("/slo-definitions/{name}", status_code=204)
async def delete_slo_definition(
    name: str,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> None:
    """Deactivate all versions of an SLO definition."""
    repo = SLORepository(session)
    existing = await repo.get_latest(name)
    if existing is None:
        raise_not_found("slo definition", name)
    await repo.deactivate(name)
