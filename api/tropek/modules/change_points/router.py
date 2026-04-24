"""Change points API — list, triage, and config endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from tropek.db.session import get_session
from tropek.modules.change_points.detector import (
    DEFAULT_ENABLED,
    DEFAULT_MAX_PVALUE,
    DEFAULT_MIN_MAGNITUDE,
    DEFAULT_MIN_SAMPLE_SIZE,
    DEFAULT_WINDOW_SIZE,
)
from tropek.modules.change_points.repository import ChangePointRepository
from tropek.modules.change_points.schemas import (
    BulkTriageRequest,
    ChangePointConfigRead,
    ChangePointConfigUpsert,
    ChangePointRead,
    TriageRequest,
)

router = APIRouter(tags=["change-points"])


@router.get("/change-points", response_model=list[ChangePointRead])
async def list_change_points(
    status: str | None = None,
    direction: str | None = None,
    asset_id: uuid.UUID | None = None,
    slo_name: str | None = None,
    metric: str | None = None,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
) -> list[ChangePointRead]:
    """List change points with optional filters."""
    repo = ChangePointRepository(session)
    rows = await repo.list_change_points(
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
    return [ChangePointRead.model_validate(row) for row in rows]


@router.patch("/change-points/bulk-triage", response_model=dict)
async def bulk_triage(
    body: BulkTriageRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Bulk-update triage state for multiple change points."""
    repo = ChangePointRepository(session)
    count = await repo.bulk_triage(
        body.ids,
        status=body.status,
        triage_note=body.triage_note,
        triage_author=body.triage_author,
    )
    await session.commit()
    return {"updated": count}


@router.get("/change-points/{change_point_id}", response_model=ChangePointRead)
async def get_change_point(
    change_point_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> ChangePointRead:
    """Get a single change point by ID."""
    repo = ChangePointRepository(session)
    row = await repo.get_by_id(change_point_id)
    if row is None:
        raise HTTPException(status_code=404, detail="change point not found")
    return ChangePointRead.model_validate(row)


@router.patch("/change-points/{change_point_id}", response_model=ChangePointRead)
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
        raise HTTPException(status_code=404, detail="change point not found")
    await session.commit()
    return ChangePointRead.model_validate(row)


@router.get("/change-points/config/defaults", response_model=ChangePointConfigRead)
async def get_default_config() -> ChangePointConfigRead:
    """Return the hardcoded default config used when no override exists."""
    return ChangePointConfigRead(
        slo_name="__default__",
        metric_name="__default__",
        enabled=DEFAULT_ENABLED,
        window_size=DEFAULT_WINDOW_SIZE,
        max_pvalue=DEFAULT_MAX_PVALUE,
        min_magnitude=DEFAULT_MIN_MAGNITUDE,
        min_sample_size=DEFAULT_MIN_SAMPLE_SIZE,
    )


@router.get(
    "/change-points/config/{slo_name}",
    response_model=list[ChangePointConfigRead],
)
async def list_config_overrides(
    slo_name: str,
    session: AsyncSession = Depends(get_session),
) -> list[ChangePointConfigRead]:
    """List all override rows for an SLO — metrics not listed use defaults."""
    repo = ChangePointRepository(session)
    configs = await repo.get_configs_for_slo(slo_name)
    return [ChangePointConfigRead.model_validate(config) for config in configs.values()]


@router.put(
    "/change-points/config/{slo_name}/{metric_name}",
    response_model=ChangePointConfigRead,
)
async def upsert_config_override(
    slo_name: str,
    metric_name: str,
    body: ChangePointConfigUpsert,
    session: AsyncSession = Depends(get_session),
) -> ChangePointConfigRead:
    """Create or update an override for a specific SLO+metric."""
    repo = ChangePointRepository(session)
    config = await repo.upsert_config(
        slo_name=slo_name,
        metric_name=metric_name,
        enabled=body.enabled if body.enabled is not None else DEFAULT_ENABLED,
        window_size=body.window_size if body.window_size is not None else DEFAULT_WINDOW_SIZE,
        max_pvalue=body.max_pvalue if body.max_pvalue is not None else DEFAULT_MAX_PVALUE,
        min_magnitude=(
            body.min_magnitude if body.min_magnitude is not None else DEFAULT_MIN_MAGNITUDE
        ),
        min_sample_size=(
            body.min_sample_size if body.min_sample_size is not None else DEFAULT_MIN_SAMPLE_SIZE
        ),
    )
    await session.commit()
    return ChangePointConfigRead.model_validate(config)


@router.delete("/change-points/config/{slo_name}/{metric_name}", status_code=204)
async def delete_config_override(
    slo_name: str,
    metric_name: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Remove an override so the metric falls back to defaults."""
    repo = ChangePointRepository(session)
    deleted = await repo.delete_config(slo_name=slo_name, metric_name=metric_name)
    if not deleted:
        raise HTTPException(status_code=404, detail="config override not found")
    await session.commit()
