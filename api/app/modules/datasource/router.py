"""FastAPI router for DataSource CRUD."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AssetGroupSLOLink, AssetSLOLink, DataSource
from app.db.session import get_session
from app.modules.assets.schemas import TagKeyCount, TagValueCount
from app.modules.common.errors import raise_conflict, raise_not_found
from app.modules.common.schemas import PagedResponse
from app.modules.datasource.repository import DataSourceRepository
from app.modules.datasource.schemas import DataSourceCreate, DataSourceRead, DataSourceUpdate

router = APIRouter()


def _ds_read(ds: DataSource) -> DataSourceRead:
    """Build a DataSourceRead with has_token derived from the ORM model."""
    r = DataSourceRead.model_validate(ds)
    r.has_token = ds.token is not None
    return r


@router.get("/datasources", response_model=PagedResponse[DataSourceRead])
async def list_datasources(
    adapter_type: str | None = None,
    tag_key: str | None = None,
    tag_val: str | None = None,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> PagedResponse[DataSourceRead]:
    """List all datasources with optional filters."""
    repo = DataSourceRepository(session)
    items = await repo.list_all(adapter_type=adapter_type, tag_key=tag_key, tag_val=tag_val)
    return PagedResponse(items=[_ds_read(d) for d in items], total=len(items))


@router.post("/datasources", response_model=DataSourceRead, status_code=201)
async def create_datasource(
    body: DataSourceCreate,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> DataSourceRead:
    """Create a new datasource."""
    repo = DataSourceRepository(session)
    ds = await repo.create(
        body.name,
        adapter_type=body.adapter_type,
        adapter_url=body.adapter_url,
        display_name=body.display_name,
        tags=body.tags,
        token=body.token,
    )
    return _ds_read(ds)


@router.get("/datasources/tag-keys", response_model=list[TagKeyCount])
async def get_tag_keys(
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> list[TagKeyCount]:
    """Return distinct tag keys with usage counts."""
    repo = DataSourceRepository(session)
    keys = await repo.get_tag_keys()
    return [TagKeyCount(key=k, count=v) for k, v in keys.items()]


@router.get("/datasources/tag-values", response_model=list[TagValueCount])
async def get_tag_values(
    key: str = Query(...),
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> list[TagValueCount]:
    """Return distinct tag values for a key with usage counts."""
    repo = DataSourceRepository(session)
    values = await repo.get_tag_values(key)
    return [TagValueCount(value=v, count=c) for v, c in values.items()]


@router.get("/datasources/{name}", response_model=DataSourceRead)
async def get_datasource(
    name: str,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> DataSourceRead:
    """Get a datasource by name."""
    repo = DataSourceRepository(session)
    ds = await repo.get_by_name(name)
    if ds is None:
        raise_not_found("datasource", name)
    return _ds_read(ds)


@router.patch("/datasources/{name}", response_model=DataSourceRead)
async def update_datasource(
    name: str,
    body: DataSourceUpdate,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> DataSourceRead:
    """Update mutable datasource fields."""
    repo = DataSourceRepository(session)
    ds = await repo.update(name, **body.model_dump(exclude_none=True))
    if ds is None:
        raise_not_found("datasource", name)
    return _ds_read(ds)


@router.delete("/datasources/{name}", status_code=204)
async def delete_datasource(
    name: str,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    """Delete a datasource by name. Returns 409 if active SLO links reference it."""
    # Check for active SLO links referencing this datasource
    asset_links = (
        (
            await session.execute(
                sa_select(AssetSLOLink).where(AssetSLOLink.data_source_name == name)
            )
        )
        .scalars()
        .all()
    )
    group_links = (
        (
            await session.execute(
                sa_select(AssetGroupSLOLink).where(AssetGroupSLOLink.data_source_name == name)
            )
        )
        .scalars()
        .all()
    )
    if asset_links or group_links:
        link_names = [lnk.link_name for lnk in asset_links] + [lnk.link_name for lnk in group_links]
        raise_conflict("datasource", name, f"referenced by SLO links: {', '.join(link_names)}")

    repo = DataSourceRepository(session)
    deleted = await repo.delete_by_name(name)
    if not deleted:
        raise_not_found("datasource", name)
    return Response(status_code=204)
