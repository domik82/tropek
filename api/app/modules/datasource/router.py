"""FastAPI router for DataSource CRUD."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.common.errors import raise_not_found
from app.modules.common.schemas import PagedResponse
from app.modules.datasource.repository import DataSourceRepository
from app.modules.datasource.schemas import DataSourceCreate, DataSourceRead, DataSourceUpdate

router = APIRouter()


@router.get("/datasources", response_model=PagedResponse[DataSourceRead])
async def list_datasources(
    adapter_type: str | None = None,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> PagedResponse[DataSourceRead]:
    """List all datasources with optional adapter_type filter."""
    repo = DataSourceRepository(session)
    items = await repo.list_all(adapter_type=adapter_type)
    return PagedResponse(items=[DataSourceRead.model_validate(d) for d in items], total=len(items))


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
        labels=body.labels,
    )
    return DataSourceRead.model_validate(ds)


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
    return DataSourceRead.model_validate(ds)


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
    return DataSourceRead.model_validate(ds)
