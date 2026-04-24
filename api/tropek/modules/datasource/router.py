"""FastAPI router for DataSource CRUD."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from tropek.db.models import DataSource
from tropek.db.session import get_session
from tropek.modules.common.exceptions import NotFoundError
from tropek.modules.common.schemas import PagedResponse, SafeQueryStr, TagKeyCount, TagValueCount
from tropek.modules.datasource.params import DataSourceCreateParams
from tropek.modules.datasource.repository import DataSourceRepository
from tropek.modules.datasource.schemas import DataSourceCreate, DataSourceRead, DataSourceUpdate

router = APIRouter()


def _ds_read(ds: DataSource) -> DataSourceRead:
    """Build a DataSourceRead with has_token derived from the ORM model."""
    r = DataSourceRead.model_validate(ds)
    r.has_token = ds.token is not None
    return r


@router.get('/datasources', response_model=PagedResponse[DataSourceRead])
async def list_datasources(
    adapter_type: SafeQueryStr | None = None,
    tag_key: SafeQueryStr | None = None,
    tag_val: SafeQueryStr | None = None,
    session: AsyncSession = Depends(get_session),
) -> PagedResponse[DataSourceRead]:
    """List all datasources with optional filters."""
    repo = DataSourceRepository(session)
    items = await repo.list_all(adapter_type=adapter_type, tag_key=tag_key, tag_val=tag_val)
    return PagedResponse(items=[_ds_read(d) for d in items], total=len(items))


@router.post('/datasources', response_model=DataSourceRead, status_code=201)
async def create_datasource(
    body: DataSourceCreate,
    session: AsyncSession = Depends(get_session),
) -> DataSourceRead:
    """Create a new datasource."""
    repo = DataSourceRepository(session)
    ds = await repo.create(
        DataSourceCreateParams(
            name=body.name,
            adapter_type=body.adapter_type,
            adapter_url=body.adapter_url,
            display_name=body.display_name,
            tags=body.tags or {},
            token=body.token,
        ),
    )
    return _ds_read(ds)


@router.get('/datasources/tag-keys', response_model=list[TagKeyCount])
async def get_tag_keys(
    session: AsyncSession = Depends(get_session),
) -> list[TagKeyCount]:
    """Return distinct tag keys with usage counts."""
    repo = DataSourceRepository(session)
    keys = await repo.get_tag_keys()
    return [TagKeyCount(key=k, count=v) for k, v in keys.items()]


@router.get('/datasources/tag-values', response_model=list[TagValueCount])
async def get_tag_values(
    key: SafeQueryStr,
    session: AsyncSession = Depends(get_session),
) -> list[TagValueCount]:
    """Return distinct tag values for a key with usage counts."""
    repo = DataSourceRepository(session)
    values = await repo.get_tag_values(key)
    return [TagValueCount(value=v, count=c) for v, c in values.items()]


@router.get('/datasources/{name}', response_model=DataSourceRead)
async def get_datasource(
    name: str,
    session: AsyncSession = Depends(get_session),
) -> DataSourceRead:
    """Get a datasource by name."""
    repo = DataSourceRepository(session)
    ds = await repo.get_by_name(name)
    if ds is None:
        raise NotFoundError('datasource', name)
    return _ds_read(ds)


@router.patch('/datasources/{name}', response_model=DataSourceRead)
async def update_datasource(
    name: str,
    body: DataSourceUpdate,
    session: AsyncSession = Depends(get_session),
) -> DataSourceRead:
    """Update mutable datasource fields."""
    repo = DataSourceRepository(session)
    ds = await repo.update(name, **body.model_dump(exclude_none=True))
    if ds is None:
        raise NotFoundError('datasource', name)
    return _ds_read(ds)


@router.delete('/datasources/{name}', status_code=204)
async def delete_datasource(
    name: str,
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Delete a datasource by name."""
    repo = DataSourceRepository(session)
    deleted = await repo.delete_by_name(name)
    if not deleted:
        raise NotFoundError('datasource', name)
    return Response(status_code=204)
