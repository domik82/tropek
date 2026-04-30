"""Change points API — list, triage, and config endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from tropek.db.session import get_session
from tropek.modules.change_points.detector import Direction
from tropek.modules.change_points.repository import (
    ChangePointListParams,
    ChangePointRepository,
)
from tropek.modules.change_points.schemas import (
    BulkTriageRequest,
    ChangePointConfigInput,
    ChangePointConfigRead,
    ChangePointRead,
    TriageRequest,
)
from tropek.modules.common.schemas import SafeQueryStr
from tropek.modules.configuration.repository import ConfigurationRepository

router = APIRouter(tags=['change-points'])


@router.get('/change-points', response_model=list[ChangePointRead])
async def list_change_points(
    status: SafeQueryStr | None = None,
    direction: Direction | None = None,
    asset_id: uuid.UUID | None = None,
    slo_name: SafeQueryStr | None = None,
    metric: SafeQueryStr | None = None,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
    limit: int = Query(default=50, ge=0, le=1000),
    offset: int = Query(default=0, ge=0, le=1_000_000),
    session: AsyncSession = Depends(get_session),
) -> list[ChangePointRead]:
    """List change points with optional filters."""
    repo = ChangePointRepository(session)
    rows = await repo.list_change_points(
        ChangePointListParams(
            status=status,
            direction=direction,
            asset_id=asset_id,
            slo_name=slo_name,
            metric_name=metric,
            from_ts=from_ts,
            to_ts=to_ts,
            limit=limit,
            offset=offset,
        )
    )
    return [ChangePointRead.model_validate(row) for row in rows]


@router.patch('/change-points/bulk-triage', response_model=dict[str, int])
async def bulk_triage(
    body: BulkTriageRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, int]:
    """Bulk-update triage state for multiple change points."""
    repo = ChangePointRepository(session)
    count = await repo.bulk_triage(
        body.ids,
        status=body.status,
        triage_note=body.triage_note,
        triage_author=body.triage_author,
    )
    await session.commit()
    return {'updated': count}


@router.get('/change-points/config/{objective_id}', response_model=ChangePointConfigRead)
async def get_change_point_config(
    objective_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> ChangePointConfigRead:
    """Get resolved change point config for an objective."""
    repo = ChangePointRepository(session)
    config = await repo.get_config_for_objective(objective_id)
    if config is not None:
        return ChangePointConfigRead.model_validate(config)
    config_repo = ConfigurationRepository(session)
    system_defaults = await config_repo.get_change_point_defaults()
    return ChangePointConfigRead(
        slo_objective_id=objective_id,
        enabled=bool(system_defaults.get('enabled', True)),
        higher_is_better=bool(system_defaults.get('higher_is_better', False)),
        window_size=int(system_defaults.get('window_size', 30)),
        max_pvalue=float(system_defaults.get('max_pvalue', 0.001)),
        min_magnitude=float(system_defaults.get('min_magnitude', 0.0)),
        min_sample_size=int(system_defaults.get('min_sample_size', 10)),
    )


@router.put('/change-points/config/{objective_id}', response_model=ChangePointConfigRead)
async def upsert_change_point_config(
    objective_id: uuid.UUID,
    body: ChangePointConfigInput,
    session: AsyncSession = Depends(get_session),
) -> ChangePointConfigRead:
    """Create or update change point config for an objective."""
    config_repo = ConfigurationRepository(session)
    system_defaults = await config_repo.get_change_point_defaults()
    repo = ChangePointRepository(session)
    config = await repo.upsert_config_for_objective(
        slo_objective_id=objective_id,
        enabled=(
            body.enabled if body.enabled is not None
            else bool(system_defaults.get('enabled', True))
        ),
        higher_is_better=(
            body.higher_is_better if body.higher_is_better is not None
            else bool(system_defaults.get('higher_is_better', False))
        ),
        window_size=(
            body.window_size if body.window_size is not None
            else int(system_defaults.get('window_size', 30))
        ),
        max_pvalue=(
            body.max_pvalue if body.max_pvalue is not None
            else float(system_defaults.get('max_pvalue', 0.001))
        ),
        min_magnitude=(
            body.min_magnitude if body.min_magnitude is not None
            else float(system_defaults.get('min_magnitude', 0.0))
        ),
        min_sample_size=(
            body.min_sample_size if body.min_sample_size is not None
            else int(system_defaults.get('min_sample_size', 10))
        ),
    )
    await session.commit()
    return ChangePointConfigRead.model_validate(config)


@router.delete('/change-points/config/{objective_id}', status_code=204)
async def delete_change_point_config(
    objective_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Remove per-objective config override. Detection falls back to system defaults."""
    repo = ChangePointRepository(session)
    deleted = await repo.delete_config_for_objective(objective_id)
    if not deleted:
        raise HTTPException(status_code=404, detail='change point config not found')
    await session.commit()


@router.get('/change-points/{change_point_id}', response_model=ChangePointRead)
async def get_change_point(
    change_point_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> ChangePointRead:
    """Get a single change point by ID."""
    repo = ChangePointRepository(session)
    row = await repo.get_by_id(change_point_id)
    if row is None:
        raise HTTPException(status_code=404, detail='change point not found')
    return ChangePointRead.model_validate(row)


@router.patch('/change-points/{change_point_id}', response_model=ChangePointRead)
async def triage_change_point(
    change_point_id: uuid.UUID,
    body: TriageRequest,
    session: AsyncSession = Depends(get_session),
) -> ChangePointRead:
    """Update triage state of a change point."""
    repo = ChangePointRepository(session)
    row = await repo.triage(
        change_point_id,
        status=body.status,
        triage_note=body.triage_note,
        linked_ticket=body.linked_ticket,
        triage_author=body.triage_author,
    )
    if row is None:
        raise HTTPException(status_code=404, detail='change point not found')
    await session.commit()
    return ChangePointRead.model_validate(row)
