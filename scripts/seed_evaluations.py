"""Seed historical evaluation data for visual inspection.

Triggers evaluations spread across 48 hours of mock data.
Two windows fall in the degraded period (2026-03-15T18:00Z - 2026-03-16T00:00Z)
to produce failures.

Evaluations are triggered window-by-window (chronological order) and each
window must complete before the next is triggered. This guarantees that
baseline comparisons always have completed predecessors available.

Usage: uv run --directory clients/python python ../../scripts/seed_evaluations.py <api_url>
"""

from __future__ import annotations

import sys
import time

from tropek_client import TropekClient

# Unique assets — POST /evaluate triggers ALL bound SLOs for an asset at once.
ASSETS = [
    # E-Commerce
    'checkout-api',
    'product-catalog',
    'user-service',
    'orders-db',
    # VM Infrastructure
    'vm-prod-web-01',
    'vm-prod-web-02',
    # Office Laptops
    'laptop-user-01',
    'laptop-user-02',
]

# 30-minute windows spread across 48h of mock data.
# Windows 5 and 6 fall in the degraded spike (18:00-00:00 on 2026-03-15).
WINDOWS = [
    ('2026-03-15T00:00:00Z', '2026-03-15T00:30:00Z'),
    ('2026-03-15T04:00:00Z', '2026-03-15T04:30:00Z'),
    ('2026-03-15T08:00:00Z', '2026-03-15T08:30:00Z'),
    ('2026-03-15T12:00:00Z', '2026-03-15T12:30:00Z'),
    ('2026-03-15T16:00:00Z', '2026-03-15T16:30:00Z'),
    ('2026-03-15T19:00:00Z', '2026-03-15T19:30:00Z'),  # degraded
    ('2026-03-15T22:00:00Z', '2026-03-15T22:30:00Z'),  # degraded
    ('2026-03-16T02:00:00Z', '2026-03-16T02:30:00Z'),
    ('2026-03-16T06:00:00Z', '2026-03-16T06:30:00Z'),
    ('2026-03-16T10:00:00Z', '2026-03-16T10:30:00Z'),
]

TERMINAL_STATUSES = {'completed', 'failed', 'partial'}


def get_eval_runs(asset_name: str) -> list[tuple[str, list[int]]]:
    """Return (evaluation_name, window_indices) pairs for this asset."""
    if 'laptop' in asset_name:
        return [('load-test', list(range(10)))]
    if 'vm-' in asset_name:
        return [
            ('user-experience', list(range(10))),
            ('optimization-testing', [0, 3, 6, 9]),
        ]
    # E-commerce
    return [
        ('load-test', list(range(10))),
        ('prod-validation', [0, 2, 4, 6, 8]),
    ]


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


def main() -> None:
    """Trigger evaluations window-by-window to ensure baselines are available."""
    if len(sys.argv) != 2:  # noqa: PLR2004
        print(f'usage: {sys.argv[0]} <api_url>', file=sys.stderr)
        sys.exit(1)

    client = TropekClient(sys.argv[1])

    # Build per-window schedule: window_index -> [(asset_name, eval_name)]
    window_jobs: dict[int, list[tuple[str, str]]] = {}
    for asset_name in ASSETS:
        for eval_name, window_indices in get_eval_runs(asset_name):
            for wi in window_indices:
                window_jobs.setdefault(wi, []).append((asset_name, eval_name))

    all_slo_eval_ids: list[str] = []
    total_windows = len(window_jobs)

    for wi in sorted(window_jobs):
        start, end = WINDOWS[wi]
        jobs = window_jobs[wi]
        print(f'Window {wi + 1}/{total_windows} ({start}) — {len(jobs)} evaluate calls')

        window_slo_ids: list[str] = []
        for asset_name, eval_name in jobs:
            result = client.evaluations.evaluate(asset_name, eval_name, start, end)
            window_slo_ids.extend(result['slo_evaluation_ids'])

        _wait_for_ids(client, window_slo_ids, f'window {wi + 1}')
        all_slo_eval_ids.extend(window_slo_ids)

    # Final summary (on individual SLO evaluations)
    results = [client.evaluations.get(str(eid)) for eid in all_slo_eval_ids]
    passed = sum(1 for e in results if e.result == 'pass')
    failed = sum(1 for e in results if e.result == 'fail')
    warning = sum(1 for e in results if e.result == 'warning')
    completed = sum(1 for e in results if e.status == 'completed')
    total = len(all_slo_eval_ids)
    print(f'seeded: {completed}/{total} completed — {passed} pass, {warning} warning, {failed} fail')


if __name__ == '__main__':
    main()
