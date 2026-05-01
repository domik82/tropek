"""Diagnostic: dump change points with their creating evaluation's timestamp.

Run while dev environment is up:
    uv run --directory api python ../scripts/debug_change_points.py

Shows which eval created each CP and how far back in history it reached.
"""

from __future__ import annotations

import asyncio
import os

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

DB_USER = os.environ.get("TK_DB_USER", "tropek_e2e")
DB_PASS = os.environ.get("TK_DB_PASSWORD", "tropek_e2e")
DB_HOST = os.environ.get("TK_DB_HOST", "localhost")
DB_PORT = os.environ.get("TK_DB_PORT", "5434")
DB_NAME = os.environ.get("TK_DB_NAME", "tropek_e2e")

DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

QUERY = text("""
    SELECT
        cp.metric_name,
        cp.period_start                   AS cp_timestamp,
        cp.direction,
        cp.change_relative_pct,
        cp.pre_segment_mean,
        cp.post_segment_mean,
        cp.created_at                     AS cp_created_at,
        cp.evaluation_run_id,
        er.eval_name                      AS creating_eval_name,
        er.period_start                   AS creating_eval_period_start,
        se.evaluation_name                AS slo_eval_name,
        se.period_start                   AS slo_eval_period_start
    FROM change_points cp
    LEFT JOIN evaluations er ON cp.evaluation_run_id = er.id
    LEFT JOIN slo_evaluations se ON cp.indicator_result_id IN (
        SELECT ir.id FROM indicator_results ir WHERE ir.slo_evaluation_id = se.id
    )
    WHERE cp.slo_name = 'http-availability-slo'
      AND cp.metric_name = 'error_rate'
    ORDER BY cp.period_start, cp.created_at
""")


async def main() -> None:
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        result = await conn.execute(QUERY)
        rows = result.fetchall()

    if not rows:
        print("No error_rate change points found.")
        return

    print(f"{'CP timestamp':<28} {'Dir':<12} {'%change':>8}  "
          f"{'pre_mean':>10} {'post_mean':>10}  "
          f"{'Created by eval_name':<25} {'Creating eval period_start':<28}")
    print("-" * 160)

    for row in rows:
        print(
            f"{str(row.cp_timestamp):<28} "
            f"{row.direction:<12} "
            f"{row.change_relative_pct:>8.2f}  "
            f"{row.pre_segment_mean:>10.6f} {row.post_segment_mean:>10.6f}  "
            f"{(row.creating_eval_name or '???'):<25} "
            f"{str(row.creating_eval_period_start or '???'):<28}"
        )

    engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
