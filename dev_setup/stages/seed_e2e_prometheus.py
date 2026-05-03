"""Trigger 7 daily evaluations against the observability stack's Prometheus data.

Resources (datasource, assets, SLI, SLO, bindings) are created by the bootstrap
manifests in dev_setup/prometheus/. This script only triggers evaluations.

Timeline: observability stack quick-test.yaml covers 2026-03-14 to 2026-03-20 (7 days).
Each evaluation covers a 30-minute window at noon. Day 7 overlaps with the outage at ~160h.

Usage: uv run --directory clients/python python ../../dev_setup/stages/seed_e2e_prometheus.py <api_url>
"""

from __future__ import annotations

import sys
import time

from tropek_client import TropekClient
from tropek_client.models import EvaluateSingleRequest

# Assets from dev_setup/prometheus manifests
ASSETS = [
    'obs-api',
    'obs-frontend',
    'obs-backend',
]

# 7 daily windows: noon to 12:30 each day across the quick-test timeline.
EVAL_WINDOWS = [
    ('2026-03-14T12:00:00Z', '2026-03-14T12:30:00Z'),
    ('2026-03-15T12:00:00Z', '2026-03-15T12:30:00Z'),
    ('2026-03-16T12:00:00Z', '2026-03-16T12:30:00Z'),
    ('2026-03-17T12:00:00Z', '2026-03-17T12:30:00Z'),
    ('2026-03-18T12:00:00Z', '2026-03-18T12:30:00Z'),
    ('2026-03-19T12:00:00Z', '2026-03-19T12:30:00Z'),
    ('2026-03-20T12:00:00Z', '2026-03-20T12:30:00Z'),
]

TERMINAL_STATUSES = {'completed', 'failed', 'partial'}


def main() -> None:
    """Trigger evaluations and poll until complete."""
    if len(sys.argv) != 2:  # noqa: PLR2004
        print(f'usage: {sys.argv[0]} <api_url>', file=sys.stderr)
        sys.exit(1)

    client = TropekClient(sys.argv[1])
    total = len(ASSETS) * len(EVAL_WINDOWS)
    print(f'Triggering {total} evaluations ({len(ASSETS)} assets x {len(EVAL_WINDOWS)} days)...')

    eval_ids: list[str] = []
    for asset_name in ASSETS:
        for start, end in EVAL_WINDOWS:
            result = client.evaluations.trigger(
                EvaluateSingleRequest(
                    asset_name=asset_name,
                    eval_name='daily-check',
                    period_start=start,
                    period_end=end,
                )
            )
            eval_ids.extend(str(eid) for eid in result.slo_evaluation_ids)

    print(f'Triggered {len(eval_ids)}, waiting for completion...')
    pending = set(eval_ids)
    for _ in range(90):
        still_pending: set[str] = set()
        for eid in pending:
            ev = client.evaluations.get(eid)
            if ev.status not in TERMINAL_STATUSES:
                still_pending.add(eid)
        pending = still_pending
        done = len(eval_ids) - len(pending)
        print(f'  {done}/{len(eval_ids)} complete...', end='\r', flush=True)
        if not pending:
            break
        time.sleep(2)

    print()
    results = [client.evaluations.get(eid) for eid in eval_ids]
    passed = sum(1 for e in results if e.result == 'pass')
    failed = sum(1 for e in results if e.result == 'fail')
    warning = sum(1 for e in results if e.result == 'warning')
    errored = sum(1 for e in results if e.status == 'failed')
    completed = sum(1 for e in results if e.status == 'completed')
    print(f'seeded: {completed}/{total} completed, {errored} failed — {passed} pass, {warning} warning, {failed} fail')


if __name__ == '__main__':
    main()
