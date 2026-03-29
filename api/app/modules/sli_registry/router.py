"""FastAPI router for SLI definition versioned CRUD."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.assets.schemas import TagKeyCount, TagValueCount
from app.modules.common.exceptions import NotFoundError
from app.modules.common.schemas import PagedResponse
from app.modules.sli_registry.repository import SLIRepository
from app.modules.sli_registry.schemas import SLIDefinitionCreate, SLIDefinitionRead

router = APIRouter()


@router.get("/sli-definitions", response_model=PagedResponse[SLIDefinitionRead])
async def list_sli_definitions(
    adapter_type: str | None = None,
    tag_key: str | None = None,
    tag_val: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> PagedResponse[SLIDefinitionRead]:
    """List all active SLI definitions."""
    repo = SLIRepository(session)
    items = await repo.list_all(adapter_type=adapter_type, tag_key=tag_key, tag_val=tag_val)
    return PagedResponse(
        items=[SLIDefinitionRead.model_validate(i) for i in items], total=len(items)
    )


@router.post("/sli-definitions", response_model=SLIDefinitionRead, status_code=201)
async def create_sli_definition(
    body: SLIDefinitionCreate,
    session: AsyncSession = Depends(get_session),
) -> SLIDefinitionRead:
    """Create a new SLI definition (or a new version if name already exists)."""
    repo = SLIRepository(session)
    sli = await repo.create(
        body.name,
        indicators=body.indicators,
        adapter_type=body.adapter_type,
        display_name=body.display_name,
        notes=body.notes,
        author=body.author,
        tags=body.tags,
        comparable_from_version=body.comparable_from_version,
    )
    return SLIDefinitionRead.model_validate(sli)


@router.get("/sli-definitions/tag-keys", response_model=list[TagKeyCount])
async def get_sli_tag_keys(
    session: AsyncSession = Depends(get_session),
) -> list[TagKeyCount]:
    """Return distinct tag keys with usage counts."""
    repo = SLIRepository(session)
    keys = await repo.get_tag_keys()
    return [TagKeyCount(key=k, count=v) for k, v in keys.items()]


@router.get("/sli-definitions/tag-values", response_model=list[TagValueCount])
async def get_sli_tag_values(
    key: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> list[TagValueCount]:
    """Return distinct tag values for a key with usage counts."""
    repo = SLIRepository(session)
    values = await repo.get_tag_values(key)
    return [TagValueCount(value=v, count=c) for v, c in values.items()]


@router.get("/sli-definitions/{name}", response_model=SLIDefinitionRead)
async def get_sli_definition(
    name: str,
    session: AsyncSession = Depends(get_session),
) -> SLIDefinitionRead:
    """Get the latest active version of an SLI definition."""
    repo = SLIRepository(session)
    sli = await repo.get_latest(name)
    if sli is None:
        raise NotFoundError("sli definition", name)
    return SLIDefinitionRead.model_validate(sli)


@router.get("/sli-definitions/{name}/versions", response_model=list[SLIDefinitionRead])
async def list_sli_versions(
    name: str,
    session: AsyncSession = Depends(get_session),
) -> list[SLIDefinitionRead]:
    """List all versions of an SLI definition."""
    repo = SLIRepository(session)
    versions = await repo.list_versions(name)
    return [SLIDefinitionRead.model_validate(v) for v in versions]


@router.delete("/sli-definitions/{name}", status_code=204)
async def delete_sli_definition(
    name: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Deactivate all versions of an SLI definition."""
    repo = SLIRepository(session)
    existing = await repo.get_latest(name)
    if existing is None:
        raise NotFoundError("sli definition", name)
    await repo.deactivate(name)
