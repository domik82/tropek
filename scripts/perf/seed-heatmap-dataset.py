"""Idempotent seeder for the Chunk C heatmap performance benchmark dataset.

Creates (or refreshes) a deterministic 1-asset x 3-SLO x 6-indicator x 200-run
dataset so every benchmark run in docs/perf/heatmap-chunk-c.md operates on
the same substrate.

Schema notes (verified against api/tropek/db/models.py):
- Asset has no ``kind`` field; ``type_name`` defaults to ``'vm'`` (seeded by migration 002).
- EvaluationRun.eval_name (not evaluation_name); no score column on the run.
- SLOEvaluation references evaluation_id (FK to evaluations.id) plus evaluation_name,
  asset_snapshot, period_start, period_end, ingestion_mode (all required).
- IndicatorResultRow references slo_objective_id (FK to slo_objectives.id) — there is
  no JSONB objective column. Each SLO therefore needs a real SLODefinition + SLOObjective
  tree before indicator rows can be inserted.

Run with:
    uv run python scripts/perf/seed-heatmap-dataset.py
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from tropek.config import get_settings
from tropek.db.models import (
    Asset,
    EvaluationRun,
    IndicatorResultRow,
    SLODefinition,
    SLOEvaluation,
    SLOObjective,
)

ASSET_NAME = 'perf-heatmap-asset'
SLO_NAMES = ('perf-slo-a', 'perf-slo-b', 'perf-slo-c')
INDICATORS_PER_SLO = 6
RUN_COUNT = 200
DAYS_SPAN = 30


async def _ensure_asset(session: AsyncSession) -> Asset:
    """Return existing perf asset or insert a new one."""
    existing_asset = (
        await session.execute(select(Asset).where(Asset.name == ASSET_NAME))
    ).scalar_one_or_none()
    if existing_asset is not None:
        return existing_asset
    new_asset = Asset(name=ASSET_NAME)
    session.add(new_asset)
    await session.flush()
    return new_asset


async def _ensure_slo_definitions(session: AsyncSession) -> dict[str, list[SLOObjective]]:
    """Return {slo_name: [SLOObjective, ...]} — creating definitions if absent.

    Each SLO gets version=1 with INDICATORS_PER_SLO objectives in sort_order 0..N-1.
    Returns only the objective list because that is all callers need for FK resolution.
    """
    slo_objectives_by_name: dict[str, list[SLOObjective]] = {}
    for slo_name in SLO_NAMES:
        existing_definition = (
            await session.execute(
                select(SLODefinition).where(
                    SLODefinition.name == slo_name,
                    SLODefinition.version == 1,
                )
            )
        ).scalar_one_or_none()
        if existing_definition is not None:
            slo_objectives_by_name[slo_name] = list(existing_definition.objectives)
            continue

        new_definition = SLODefinition(
            name=slo_name,
            version=1,
            comparable_from_version=1,
            total_score_pass_threshold=90.0,
            total_score_warning_threshold=75.0,
        )
        session.add(new_definition)
        await session.flush()

        objectives: list[SLOObjective] = []
        for indicator_index in range(INDICATORS_PER_SLO):
            objective = SLOObjective(
                slo_definition_id=new_definition.id,
                sli=f'metric_{indicator_index}',
                display_name=f'Metric {indicator_index}',
                weight=1,
                key_sli=(indicator_index == 0),
                sort_order=indicator_index,
                pass_threshold=[f'<{600 + indicator_index * 50}'],
                warning_threshold=[f'<{800 + indicator_index * 50}'],
            )
            session.add(objective)
            objectives.append(objective)
        await session.flush()
        slo_objectives_by_name[slo_name] = objectives

    return slo_objectives_by_name


async def _count_existing_runs(session: AsyncSession, asset_id: uuid.UUID) -> int:
    """Return the number of EvaluationRun rows already seeded for this asset."""
    existing_run_ids = (
        await session.execute(
            select(EvaluationRun.id).where(EvaluationRun.asset_id == asset_id)
        )
    ).scalars().all()
    return len(existing_run_ids)


async def _seed_runs(
    session: AsyncSession,
    asset: Asset,
    slo_objectives_by_name: dict[str, list[SLOObjective]],
) -> None:
    """Insert EvaluationRun + SLOEvaluation + IndicatorResultRow rows.

    Idempotent: exits early if the asset already has >= RUN_COUNT runs.
    """
    if await _count_existing_runs(session, asset.id) >= RUN_COUNT:
        return

    now = datetime.now(UTC)
    time_step = timedelta(days=DAYS_SPAN) / RUN_COUNT
    asset_snapshot = {'name': ASSET_NAME, 'type_name': 'vm'}

    for run_index in range(RUN_COUNT):
        period_end = now - time_step * (RUN_COUNT - run_index - 1)
        period_start = period_end - timedelta(minutes=15)
        eval_name = 'daily' if run_index % 2 == 0 else 'hourly'

        evaluation_run = EvaluationRun(
            id=uuid.uuid4(),
            asset_id=asset.id,
            eval_name=eval_name,
            period_start=period_start,
            period_end=period_end,
            status='completed',
            result='pass',
            achieved_points=27,
            total_points=30,
        )
        session.add(evaluation_run)
        await session.flush()

        for slo_offset, slo_name in enumerate(SLO_NAMES):
            slo_result = 'pass' if (run_index + slo_offset) % 4 else 'warning'
            slo_evaluation = SLOEvaluation(
                id=uuid.uuid4(),
                evaluation_id=evaluation_run.id,
                evaluation_name=eval_name,
                asset_id=asset.id,
                asset_snapshot=asset_snapshot,
                period_start=period_start,
                period_end=period_end,
                slo_name=slo_name,
                slo_version=1,
                sli_version=1,
                status='completed',
                result=slo_result,
                score=90.0,
                achieved_points=9,
                total_points=10,
                ingestion_mode='pull',
                job_stats={'sli_metadata': {}},
            )
            session.add(slo_evaluation)
            await session.flush()

            for indicator_index, objective in enumerate(slo_objectives_by_name[slo_name]):
                indicator_status = 'pass' if (indicator_index + run_index) % 5 else 'warning'
                indicator_score = 100.0 if (indicator_index + run_index) % 5 else 60.0
                indicator_row = IndicatorResultRow(
                    id=uuid.uuid4(),
                    slo_evaluation_id=slo_evaluation.id,
                    slo_objective_id=objective.id,
                    status=indicator_status,
                    score=indicator_score,
                    value=250.0 + indicator_index * 10 + (run_index % 20),
                    compared_value=240.0 + indicator_index * 10,
                    change_relative_pct=4.0,
                )
                session.add(indicator_row)
            await session.flush()


async def main() -> None:
    """Seed the benchmark dataset against the configured database."""
    settings = get_settings()
    engine = create_async_engine(settings.database.async_url, echo=False)
    async_session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session_factory() as session:
        asset = await _ensure_asset(session)
        slo_objectives_by_name = await _ensure_slo_definitions(session)
        await _seed_runs(session, asset, slo_objectives_by_name)
        await session.commit()

    await engine.dispose()
    print(f'seeded dataset for asset={ASSET_NAME}')


if __name__ == '__main__':
    asyncio.run(main())
