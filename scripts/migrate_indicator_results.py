"""One-time data migration: indicator_results JSONB → normalized table.

Run with: uv run python scripts/migrate_indicator_results.py
"""

from __future__ import annotations

import asyncio
import logging
import uuid

from tropek.config import get_settings
from tropek.db.models import Evaluation, IndicatorResultRow, SLODefinition, SLOObjective
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)


async def _resolve_objectives(
    session: AsyncSession,
    slo_name: str,
    slo_version: int | None,
    created_at,
) -> dict[str, uuid.UUID]:
    """Build metric_name -> objective_id lookup for this evaluation's SLO."""
    if slo_version is not None:
        q = (
            select(SLOObjective)
            .join(SLODefinition)
            .where(SLODefinition.name == slo_name, SLODefinition.version == slo_version)
        )
    else:
        # Fallback: latest version at or before evaluation creation time
        version_q = select(func.max(SLODefinition.version)).where(
            SLODefinition.name == slo_name, SLODefinition.created_at <= created_at
        )
        version = (await session.execute(version_q)).scalar_one_or_none()
        if version is None:
            # Last resort: current latest version
            version_q = select(func.max(SLODefinition.version)).where(SLODefinition.name == slo_name)
            version = (await session.execute(version_q)).scalar_one_or_none()
            if version is None:
                return {}
            logger.warning(
                'No SLO version found at eval time for %s, using latest v%d',
                slo_name,
                version,
            )
        q = (
            select(SLOObjective)
            .join(SLODefinition)
            .where(SLODefinition.name == slo_name, SLODefinition.version == version)
        )

    rows = await session.execute(q)
    return {obj.sli: obj.id for obj in rows.scalars().all()}


async def migrate(session: AsyncSession) -> tuple[int, int]:
    """Migrate all evaluations with JSONB indicator_results to normalized table.

    Returns (migrated_count, skipped_count).
    """
    # Only migrate evaluations that have JSONB data but no normalized rows yet
    q = (
        select(Evaluation)
        .where(
            Evaluation.indicator_results.isnot(None),
            Evaluation.indicator_results != [],
        )
        .outerjoin(IndicatorResultRow, IndicatorResultRow.evaluation_id == Evaluation.id)
        .group_by(Evaluation.id)
        .having(func.count(IndicatorResultRow.id) == 0)
        .order_by(Evaluation.created_at)
    )
    result = await session.execute(q)
    evals = list(result.scalars().all())

    migrated = 0
    skipped = 0
    obj_cache: dict[tuple[str, int | None], dict[str, uuid.UUID]] = {}

    for ev in evals:
        cache_key = (ev.slo_name, ev.slo_version)
        if cache_key not in obj_cache:
            obj_cache[cache_key] = await _resolve_objectives(
                session,
                ev.slo_name,
                ev.slo_version,
                ev.created_at,
            )
        obj_lookup = obj_cache[cache_key]

        if not obj_lookup:
            logger.warning(
                'No objectives found for eval %s (slo=%s, v=%s)',
                ev.id,
                ev.slo_name,
                ev.slo_version,
            )
            skipped += 1
            continue

        for ir in ev.indicator_results:
            metric = ir.get('metric', '')
            obj_id = obj_lookup.get(metric)
            if obj_id is None:
                logger.warning('No objective match for metric %r in eval %s', metric, ev.id)
                continue
            session.add(
                IndicatorResultRow(
                    evaluation_id=ev.id,
                    slo_objective_id=obj_id,
                    value=ir.get('value'),
                    compared_value=ir.get('compared_value'),
                    change_absolute=ir.get('change_absolute'),
                    change_relative_pct=ir.get('change_relative_pct'),
                    status=ir.get('status', 'error'),
                    score=ir.get('score', 0.0),
                )
            )
        migrated += 1

        # Flush in batches of 100
        if migrated % 100 == 0:
            await session.flush()
            logger.info('Migrated %d evaluations...', migrated)

    await session.flush()
    return migrated, skipped


async def main() -> None:
    """Run the migration against the configured database."""
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    engine = create_async_engine(settings.db.url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session, session.begin():
        migrated, skipped = await migrate(session)
        logger.info('Migration complete: %d migrated, %d skipped', migrated, skipped)

    await engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
