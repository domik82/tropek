"""FastAPI router for SLI definition versioned CRUD."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.common.errors import raise_not_found
from app.modules.common.schemas import PagedResponse
from app.modules.sli_registry.repository import SLIRepository
from app.modules.sli_registry.schemas import SLIDefinitionCreate, SLIDefinitionRead

router = APIRouter()


@router.get("/sli-definitions", response_model=PagedResponse[SLIDefinitionRead])
async def list_sli_definitions(
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> PagedResponse[SLIDefinitionRead]:
    """List all active SLI definitions."""
    repo = SLIRepository(session)
    items = await repo.list_all()
    return PagedResponse(
        items=[SLIDefinitionRead.model_validate(i) for i in items], total=len(items)
    )


@router.post("/sli-definitions", response_model=SLIDefinitionRead, status_code=201)
async def create_sli_definition(
    body: SLIDefinitionCreate,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> SLIDefinitionRead:
    """Create a new SLI definition (or a new version if name already exists)."""
    repo = SLIRepository(session)
    sli = await repo.create(
        body.name,
        indicators=body.indicators,
        display_name=body.display_name,
        notes=body.notes,
        author=body.author,
        meta=body.meta,
    )
    return SLIDefinitionRead.model_validate(sli)


@router.get("/sli-definitions/{name}", response_model=SLIDefinitionRead)
async def get_sli_definition(
    name: str,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> SLIDefinitionRead:
    """Get the latest active version of an SLI definition."""
    repo = SLIRepository(session)
    sli = await repo.get_latest(name)
    if sli is None:
        raise_not_found("sli definition", name)
    return SLIDefinitionRead.model_validate(sli)


@router.get("/sli-definitions/{name}/versions", response_model=list[SLIDefinitionRead])
async def list_sli_versions(
    name: str,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> list[SLIDefinitionRead]:
    """List all versions of an SLI definition."""
    repo = SLIRepository(session)
    versions = await repo.list_versions(name)
    return [SLIDefinitionRead.model_validate(v) for v in versions]


@router.delete("/sli-definitions/{name}", status_code=204)
async def delete_sli_definition(
    name: str,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> None:
    """Deactivate all versions of an SLI definition."""
    repo = SLIRepository(session)
    existing = await repo.get_latest(name)
    if existing is None:
        raise_not_found("sli definition", name)
    await repo.deactivate(name)
