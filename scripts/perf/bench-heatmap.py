"""Chunk C benchmark harness — http latency + in-process cProfile.

Usage:
    uv run python scripts/perf/bench-heatmap.py http
    uv run python scripts/perf/bench-heatmap.py profile

Both commands print markdown ready to paste into docs/perf/heatmap-chunk-c.md.
"""

from __future__ import annotations

import asyncio
import cProfile
import io
import os
import pstats
import resource
import statistics
import sys
import time

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from tropek.config import get_settings
from tropek.modules.assets.repository import AssetRepository
from tropek.modules.quality_gate.repositories.trend import TrendRepository
from tropek.modules.quality_gate.workflows.presentation.presenter import (
    build_grouped_heatmap_response,
)

ASSET_NAME = 'perf-heatmap-asset'
API_BASE = os.environ.get('TROPEK_API_BASE', 'http://localhost:9080')
URL = f'{API_BASE}/evaluate/metric-heatmap?asset_name={ASSET_NAME}'
URL_UNCACHED = URL + '&cache=false'
WARMUP = 10
SAMPLES = 100
PROFILE_ITERATIONS = 50


def _measure(url: str, label: str) -> None:
    """Run WARMUP + SAMPLES serial requests and print markdown latency table."""
    with httpx.Client(timeout=30.0) as client:
        for _ in range(WARMUP):
            client.get(url).read()
        latencies_ms: list[float] = []
        payload_bytes = 0
        for _ in range(SAMPLES):
            start = time.perf_counter()
            payload_bytes = len(client.get(url).read())
            latencies_ms.append((time.perf_counter() - start) * 1000)
    latencies_ms.sort()

    def percentile(fraction: float) -> float:
        return latencies_ms[int(len(latencies_ms) * fraction) - 1]

    print(f'### {label}')
    print('| metric | value |')
    print('|---|---|')
    print(f'| p50 latency (ms) | {percentile(0.50):.1f} |')
    print(f'| p95 latency (ms) | {percentile(0.95):.1f} |')
    print(f'| p99 latency (ms) | {percentile(0.99):.1f} |')
    print(f'| mean latency (ms) | {statistics.mean(latencies_ms):.1f} |')
    print(f'| payload bytes | {payload_bytes} |')
    print()


def run_http() -> None:
    """Measure end-to-end HTTP latency for cached and uncached paths."""
    _measure(URL, 'cache=true (default)')
    _measure(URL_UNCACHED, 'cache=false (bypass)')


async def run_profile() -> None:
    """Profile build_grouped_heatmap_response in-process via cProfile."""
    settings = get_settings()
    engine = create_async_engine(settings.database.async_url, echo=False)
    async_session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session_factory() as session:
        asset = await AssetRepository(session).get_by_name(ASSET_NAME)
        assert asset is not None, 'seed dataset first (run seed-heatmap-dataset.py)'
        trend_repo = TrendRepository(session)
        runs = await trend_repo.get_grouped_metric_heatmap(asset_id=asset.id)
        run_ids = [run.id for run in runs]
        noted_run_ids = await trend_repo.get_run_ids_with_notes(run_ids)
    await engine.dispose()

    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(PROFILE_ITERATIONS):
        build_grouped_heatmap_response(ASSET_NAME, runs, noted_run_ids=noted_run_ids)
    profiler.disable()
    rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    profile_stream = io.StringIO()
    pstats.Stats(profiler, stream=profile_stream).sort_stats('cumulative').print_stats(15)
    print(f'### cProfile top 15 (cumulative) — {PROFILE_ITERATIONS} iterations')
    print('```')
    print(profile_stream.getvalue())
    print('```')
    print(f'| rss delta (KB) | {rss_after - rss_before} |')


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'http'
    if mode == 'profile':
        asyncio.run(run_profile())
    else:
        run_http()
