r"""Eager backfill for the heatmap column cache.

Run once per environment after deploying the per-column cache. Iterates every
completed evaluation_run, builds its fragment, and writes it to Redis.
Idempotent — re-running refreshes TTL and catches any fragments evicted by
memory pressure.

Usage:
    uv run python scripts/perf/warm-heatmap-cache.py
    uv run python scripts/perf/warm-heatmap-cache.py --asset-name perf-heatmap-asset
    uv run python scripts/perf/warm-heatmap-cache.py --dry-run

Exit codes:
    0 — success (all completed runs cached)
    1 — partial failure (some fragments failed to build; re-run safely)

Environment: reads TK_* env vars the same way the API does. Example against
a local dev environment:

    TK_DB_USER=tropek TK_DB_PASSWORD=tropek \\
      TK_DB_HOST=localhost TK_DB_PORT=5432 TK_DB_NAME=tropek \\
      TK_REDIS_PASSWORD=redis_password TK_REDIS_HOST=localhost TK_REDIS_PORT=6379 \\
      TK_SECRET_KEY=dev-key TK_CONFIG_PATH=config.yaml \\
      uv run --directory api python ../scripts/perf/warm-heatmap-cache.py
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import uuid

import redis.asyncio as redis_async
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from tropek.config import get_settings
from tropek.db.models import Asset, EvaluationRun
from tropek.modules.quality_gate.evaluation_engine.constants import EvaluationStatus
from tropek.modules.quality_gate.repositories.trend import TrendRepository
from tropek.modules.quality_gate.workflows.presentation.heatmap_cache import (
    HeatmapColumnCache,
)
from tropek.modules.quality_gate.workflows.presentation.presenter import (
    build_column_fragment,
)

BATCH_SIZE = 50

logger = logging.getLogger('warm-heatmap-cache')


async def _list_asset_ids(
    session: AsyncSession, asset_name: str | None
) -> list[uuid.UUID]:
    """Return the list of asset ids to warm (one if filtered, all otherwise)."""
    if asset_name is not None:
        asset_id_result = await session.execute(
            select(Asset.id).where(Asset.name == asset_name)
        )
        found_id = asset_id_result.scalar_one_or_none()
        if found_id is None:
            print(f'asset not found: {asset_name}', file=sys.stderr)
            sys.exit(1)
        return [found_id]
    all_ids_result = await session.execute(select(Asset.id))
    return list(all_ids_result.scalars().all())


async def _list_all_completed_run_ids(
    session: AsyncSession, asset_id: uuid.UUID
) -> list[uuid.UUID]:
    """Return ids of every completed EvaluationRun for an asset with no safety cap.

    ``TrendRepository.list_runs_for_heatmap`` applies a 100-run cap when no
    date range is given, which would silently truncate large datasets. This
    query fetches only the ids (lightweight) with no cap so the backfill covers
    the full history.
    """
    completed_runs_result = await session.execute(
        select(EvaluationRun.id)
        .where(
            EvaluationRun.asset_id == asset_id,
            EvaluationRun.status == EvaluationStatus.COMPLETED,
        )
        .order_by(EvaluationRun.period_start.desc())
    )
    return list(completed_runs_result.scalars().all())


async def _warm_asset(
    session: AsyncSession,
    cache: HeatmapColumnCache,
    asset_id: uuid.UUID,
    *,
    dry_run: bool,
) -> tuple[int, int]:
    """Warm every completed run for one asset. Returns (warmed, failed).

    Fetches all completed run ids first (no cap), then batches the heavy
    joined query in BATCH_SIZE chunks via run_id_filter — which bypasses the
    100-run safety cap in get_grouped_metric_heatmap. This keeps peak memory
    bounded while covering the full run history.
    """
    trend_repository = TrendRepository(session)
    all_completed_run_ids = await _list_all_completed_run_ids(session, asset_id)

    warmed = 0
    failed = 0
    for batch_start in range(0, len(all_completed_run_ids), BATCH_SIZE):
        batch_run_ids = all_completed_run_ids[batch_start : batch_start + BATCH_SIZE]
        runs = await trend_repository.get_grouped_metric_heatmap(
            asset_id=asset_id, run_id_filter=batch_run_ids
        )
        fragments = []
        for run in runs:
            try:
                fragment = build_column_fragment(run, has_notes=False)
                fragments.append(fragment)
                warmed += 1
            except Exception as exc:  # noqa: BLE001 — single bad run must not halt the entire backfill
                logger.warning('build failed for run %s: %s', run.id, exc)
                failed += 1
        if fragments and not dry_run:
            await cache.set_many(fragments)
    return warmed, failed


async def _warm(asset_name: str | None, dry_run: bool) -> int:
    """Run the full backfill. Returns exit code (0 = success, 1 = partial failure)."""
    settings = get_settings()
    engine = create_async_engine(settings.database.async_url, echo=False)
    async_session_factory = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    redis_client = redis_async.from_url(settings.cache.url)
    cache = HeatmapColumnCache(
        redis_client, ttl_seconds=settings.cache.ttl.heatmap_column
    )

    total_warmed = 0
    total_failed = 0
    async with async_session_factory() as session:
        asset_ids = await _list_asset_ids(session, asset_name)
        for asset_id in asset_ids:
            warmed, failed = await _warm_asset(
                session, cache, asset_id, dry_run=dry_run
            )
            total_warmed += warmed
            total_failed += failed

    await redis_client.aclose()
    await engine.dispose()
    action = 'would warm' if dry_run else 'warmed'
    print(f'{action} {total_warmed} fragments ({total_failed} failed)')
    return 1 if total_failed else 0


def main() -> None:
    """Parse arguments and run the cache backfill."""
    parser = argparse.ArgumentParser(description='Warm the heatmap column cache')
    parser.add_argument('--asset-name', default=None, help='Limit to one asset')
    parser.add_argument(
        '--dry-run', action='store_true', help='Count fragments, do not write'
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    sys.exit(asyncio.run(_warm(args.asset_name, args.dry_run)))


if __name__ == '__main__':
    main()
