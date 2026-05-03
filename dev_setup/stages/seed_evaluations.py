"""Seed historical evaluation data for visual inspection.

Triggers evaluations spread across 48 hours of mock data.
Two windows fall in the degraded period (2026-03-15T18:00Z - 2026-03-16T00:00Z)
to produce failures.

Each evaluation pattern declares its own named schedule with explicit timestamps.
Evaluations are triggered window-by-window (chronological order) and each
window must complete before the next is triggered. This guarantees that
baseline comparisons always have completed predecessors available.

Usage: uv run --directory clients/python python ../../dev_setup/stages/seed_evaluations.py <api_url>
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from tropek_client import TropekClient
from tropek_client.models import AnnotationCreate, EvaluateSingleRequest, EvaluationSummary

TERMINAL_STATUSES = {'completed', 'failed', 'partial'}


# ---------------------------------------------------------------------------
# Evaluation schedules — each pattern has its own explicit time windows
# ---------------------------------------------------------------------------

LOAD_TEST_SCHEDULE = [
    ('2026-03-14T00:00:00Z', '2026-03-14T00:30:00Z'),
    ('2026-03-14T04:00:00Z', '2026-03-14T04:30:00Z'),
    ('2026-03-14T08:00:00Z', '2026-03-14T08:30:00Z'),
    ('2026-03-14T12:00:00Z', '2026-03-14T12:30:00Z'),
    ('2026-03-14T16:00:00Z', '2026-03-14T16:30:00Z'),
    ('2026-03-14T20:00:00Z', '2026-03-14T20:30:00Z'),
    ('2026-03-15T00:00:00Z', '2026-03-15T00:30:00Z'),
    ('2026-03-15T04:00:00Z', '2026-03-15T04:30:00Z'),
    ('2026-03-15T08:00:00Z', '2026-03-15T08:30:00Z'),
    ('2026-03-15T12:00:00Z', '2026-03-15T12:30:00Z'),
    ('2026-03-15T16:00:00Z', '2026-03-15T16:30:00Z'),
    ('2026-03-15T19:00:00Z', '2026-03-15T19:30:00Z'),  # degraded period
    ('2026-03-15T22:00:00Z', '2026-03-15T22:30:00Z'),  # degraded period
    ('2026-03-16T02:00:00Z', '2026-03-16T02:30:00Z'),
    ('2026-03-16T06:00:00Z', '2026-03-16T06:30:00Z'),
    ('2026-03-16T10:00:00Z', '2026-03-16T10:30:00Z'),
    ('2026-03-16T14:00:00Z', '2026-03-16T14:30:00Z'),
]

PROD_VALIDATION_SCHEDULE = [
    ('2026-03-15T00:00:00Z', '2026-03-15T00:30:00Z'),
    ('2026-03-15T08:00:00Z', '2026-03-15T08:30:00Z'),
    ('2026-03-15T16:00:00Z', '2026-03-15T16:30:00Z'),
    ('2026-03-15T22:00:00Z', '2026-03-15T22:30:00Z'),  # degraded period
    ('2026-03-16T06:00:00Z', '2026-03-16T06:30:00Z'),
]

FEATURE_BRANCH_SCHEDULE = [
    ('2026-03-16T02:00:00Z', '2026-03-16T02:30:00Z'),
    ('2026-03-16T06:00:00Z', '2026-03-16T06:30:00Z'),
    ('2026-03-16T10:00:00Z', '2026-03-16T10:30:00Z'),
]

USER_EXPERIENCE_SCHEDULE = [
    ('2026-03-15T00:00:00Z', '2026-03-15T00:30:00Z'),
    ('2026-03-15T04:00:00Z', '2026-03-15T04:30:00Z'),
    ('2026-03-15T08:00:00Z', '2026-03-15T08:30:00Z'),
    ('2026-03-15T12:00:00Z', '2026-03-15T12:30:00Z'),
    ('2026-03-15T16:00:00Z', '2026-03-15T16:30:00Z'),
    ('2026-03-15T19:00:00Z', '2026-03-15T19:30:00Z'),
    ('2026-03-15T22:00:00Z', '2026-03-15T22:30:00Z'),
    ('2026-03-16T02:00:00Z', '2026-03-16T02:30:00Z'),
    ('2026-03-16T06:00:00Z', '2026-03-16T06:30:00Z'),
    ('2026-03-16T10:00:00Z', '2026-03-16T10:30:00Z'),
]

OPTIMIZATION_TESTING_SCHEDULE = [
    ('2026-03-15T00:00:00Z', '2026-03-15T00:30:00Z'),
    ('2026-03-15T12:00:00Z', '2026-03-15T12:30:00Z'),
    ('2026-03-15T22:00:00Z', '2026-03-15T22:30:00Z'),
    ('2026-03-16T10:00:00Z', '2026-03-16T10:30:00Z'),
]


# ---------------------------------------------------------------------------
# Evaluation pattern definition
# ---------------------------------------------------------------------------


@dataclass
class EvalPattern:
    """A named evaluation pattern with schedule and optional cross-series comparison."""

    eval_name: str
    schedule: list[tuple[str, str]]
    compare_to: dict[str, str] | None = None


# ---------------------------------------------------------------------------
# Per-asset evaluation patterns
# ---------------------------------------------------------------------------

ECOMMERCE_ASSETS = ['checkout-api', 'product-catalog', 'user-service', 'orders-db']
VM_ASSETS = ['vm-prod-web-01', 'vm-prod-web-02']
LAPTOP_ASSETS = ['laptop-user-01', 'laptop-user-02']


def get_patterns_for_asset(asset_name: str) -> list[EvalPattern]:
    """Return evaluation patterns for a given asset."""
    if asset_name in ECOMMERCE_ASSETS:
        return [
            EvalPattern('load-test', LOAD_TEST_SCHEDULE),
            EvalPattern('prod-validation', PROD_VALIDATION_SCHEDULE),
            EvalPattern(
                'feature-branch-test',
                FEATURE_BRANCH_SCHEDULE,
                compare_to={'evaluation_name': 'load-test'},
            ),
        ]
    if asset_name in VM_ASSETS:
        return [
            EvalPattern('user-experience', USER_EXPERIENCE_SCHEDULE),
            EvalPattern('optimization-testing', OPTIMIZATION_TESTING_SCHEDULE),
        ]
    if asset_name in LAPTOP_ASSETS:
        return [EvalPattern('load-test', LOAD_TEST_SCHEDULE)]
    return []


ALL_ASSETS = ECOMMERCE_ASSETS + VM_ASSETS + LAPTOP_ASSETS


# ---------------------------------------------------------------------------
# Execution helpers
# ---------------------------------------------------------------------------


@dataclass
class ScheduledJob:
    """A single evaluation trigger scheduled at a specific time window."""

    asset_name: str
    eval_name: str
    start: str
    end: str
    compare_to: dict[str, str] | None = None


def build_chronological_schedule() -> list[list[ScheduledJob]]:
    """Merge all asset patterns into chronological window groups.

    Returns a list of window groups, each containing all jobs that share
    the same start timestamp. Groups are sorted chronologically.
    """
    jobs_by_start: dict[str, list[ScheduledJob]] = {}
    for asset_name in ALL_ASSETS:
        for pattern in get_patterns_for_asset(asset_name):
            for start, end in pattern.schedule:
                job = ScheduledJob(
                    asset_name=asset_name,
                    eval_name=pattern.eval_name,
                    start=start,
                    end=end,
                    compare_to=pattern.compare_to,
                )
                jobs_by_start.setdefault(start, []).append(job)

    return [jobs_by_start[key] for key in sorted(jobs_by_start)]


def _wait_for_ids(client: TropekClient, eval_ids: list[str], label: str) -> None:
    """Poll until all SLO evaluation IDs reach a terminal status."""
    pending = set(eval_ids)
    for _ in range(180):
        still_pending: set[str] = set()
        for eid in pending:
            ev = client.evaluations.get(str(eid))
            if ev.status not in TERMINAL_STATUSES:
                still_pending.add(eid)
        pending = still_pending
        done = len(eval_ids) - len(pending)
        print(f'  {label}: {done}/{len(eval_ids)} complete...', end='\r', flush=True)
        if not pending:
            break
        time.sleep(1)
    print()


# ---------------------------------------------------------------------------
# Lab monitor (90-day series, separate from the main schedule)
# ---------------------------------------------------------------------------

LAB_START = datetime.fromisoformat('2025-12-16T12:00:00+00:00')
LAB_DAYS = 90
LAB_WINDOW_MINUTES = 30


def _seed_lab_monitor(client: TropekClient) -> list[str]:
    """Seed 90 daily evaluations for lab-monitor-01."""
    all_ids: list[str] = []
    for day in range(LAB_DAYS):
        start = LAB_START + timedelta(days=day)
        end = start + timedelta(minutes=LAB_WINDOW_MINUTES)
        start_str = start.strftime('%Y-%m-%dT%H:%M:%SZ')
        end_str = end.strftime('%Y-%m-%dT%H:%M:%SZ')

        print(f'  lab-monitor day {day + 1}/{LAB_DAYS} ({start_str})', end='\r', flush=True)
        result = client.evaluations.trigger(
            EvaluateSingleRequest(
                asset_name='lab-monitor-01',
                eval_name='daily-lab',
                period_start=start_str,
                period_end=end_str,
            )
        )
        slo_ids = [str(sid) for sid in result.slo_evaluation_ids]
        _wait_for_ids(client, slo_ids, f'lab day {day + 1}')
        all_ids.extend(slo_ids)

    print()
    return all_ids


# ---------------------------------------------------------------------------
# Annotations
# ---------------------------------------------------------------------------


def _seed_example_annotations(
    client: TropekClient,
    results: list[EvaluationSummary],
) -> None:
    """Attach annotations across visible categories so trend charts show pins in dev."""
    categories = client.annotation_categories.list()
    categories_by_name: dict[str, Any] = {category.name: str(category.id) for category in categories}
    required = ['info', 'failure', 'investigation']
    if not all(name in categories_by_name for name in required):
        print('skipping annotation seeding: required default categories missing')
        return

    completed = [ev for ev in results if ev.status == 'completed']
    if len(completed) < 3:  # noqa: PLR2004
        return

    seen_runs: list[str] = []
    for ev in sorted(completed, key=lambda e: e.created_at, reverse=True):
        run_id = str(ev.evaluation_id)
        if run_id not in seen_runs:
            seen_runs.append(run_id)
        if len(seen_runs) == 3:  # noqa: PLR2004
            break

    if len(seen_runs) < 3:  # noqa: PLR2004
        return

    annotations = [
        (seen_runs[0], 'Routine deployment', categories_by_name['info']),
        (seen_runs[1], 'Investigating timeout spike', categories_by_name['investigation']),
        (seen_runs[2], 'Known flake — p99 latency', categories_by_name['failure']),
    ]
    for run_id, content, category_id in annotations:
        client.annotations.create_for_run(
            run_id,
            AnnotationCreate(content=content, author='seed', category_id=category_id),
        )
    print(f'seeded {len(annotations)} example annotations across info/investigation/failure')


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Trigger evaluations window-by-window to ensure baselines are available."""
    if len(sys.argv) != 2:  # noqa: PLR2004
        print(f'usage: {sys.argv[0]} <api_url>', file=sys.stderr)
        sys.exit(1)

    client = TropekClient(sys.argv[1])

    window_groups = build_chronological_schedule()
    all_slo_eval_ids: list[str] = []

    for group_index, jobs in enumerate(window_groups):
        timestamp = jobs[0].start
        print(f'Window {group_index + 1}/{len(window_groups)} ({timestamp}) — {len(jobs)} triggers')

        window_slo_ids: list[str] = []
        for job in jobs:
            result = client.evaluations.trigger(
                EvaluateSingleRequest(
                    asset_name=job.asset_name,
                    eval_name=job.eval_name,
                    period_start=job.start,
                    period_end=job.end,
                    compare_to=job.compare_to,
                )
            )
            window_slo_ids.extend(str(sid) for sid in result.slo_evaluation_ids)

        _wait_for_ids(client, window_slo_ids, f'window {group_index + 1}')
        all_slo_eval_ids.extend(window_slo_ids)

    # Seed lab-monitor-01 with 90 daily evaluations
    print('Seeding lab-monitor-01 (90 days)...')
    lab_ids = _seed_lab_monitor(client)
    all_slo_eval_ids.extend(lab_ids)

    # Final summary (on individual SLO evaluations)
    results = [client.evaluations.get(str(eid)) for eid in all_slo_eval_ids]
    passed = sum(1 for e in results if e.result == 'pass')
    failed = sum(1 for e in results if e.result == 'fail')
    warning = sum(1 for e in results if e.result == 'warning')
    completed = sum(1 for e in results if e.status == 'completed')
    total = len(all_slo_eval_ids)
    print(f'seeded: {completed}/{total} completed — {passed} pass, {warning} warning, {failed} fail')

    _seed_example_annotations(client, results)


if __name__ == '__main__':
    main()
