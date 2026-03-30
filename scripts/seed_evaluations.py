"""Seed historical evaluation data for visual inspection.

Triggers evaluations spread across 48 hours of mock data.
Two windows fall in the degraded period (2026-03-15T18:00Z - 2026-03-16T00:00Z)
to produce failures.

Usage: uv run --directory clients/python python ../../scripts/seed_evaluations.py <api_url>
"""

from __future__ import annotations

import sys
import time

from tropek_client import TropekClient

# (asset_name, slo_name) pairs matching the bootstrap SLO links
ASSETS = [
    # E-Commerce (existing)
    ("checkout-api", "http-availability-slo"),
    ("checkout-api", "agg-latency-slo"),
    ("product-catalog", "http-availability-slo"),
    ("user-service", "http-availability-slo"),
    ("orders-db", "db-performance-slo"),
    # VM Infrastructure
    ("vm-prod-web-01", "vm-health-slo"),
    ("vm-prod-web-02", "vm-health-slo"),
    ("vm-prod-web-03", "vm-health-slo"),
    ("vm-prod-web-04", "vm-health-slo"),
    ("vm-prod-web-05", "vm-health-slo"),
    # Office Laptops — one app SLO per laptop (bindings are via office-laptops group)
    ("laptop-user-01", "office-word-health-slo"),
    ("laptop-user-02", "office-excel-health-slo"),
    ("laptop-user-03", "office-powerpoint-health-slo"),
    ("laptop-user-04", "office-outlook-health-slo"),
    ("laptop-user-05", "office-word-health-slo"),
]

# 30-minute windows spread across 48h of mock data.
# Windows 5 and 6 fall in the degraded spike (18:00-00:00 on 2026-03-15).
WINDOWS = [
    ("2026-03-15T00:00:00Z", "2026-03-15T00:30:00Z"),
    ("2026-03-15T04:00:00Z", "2026-03-15T04:30:00Z"),
    ("2026-03-15T08:00:00Z", "2026-03-15T08:30:00Z"),
    ("2026-03-15T12:00:00Z", "2026-03-15T12:30:00Z"),
    ("2026-03-15T16:00:00Z", "2026-03-15T16:30:00Z"),
    ("2026-03-15T19:00:00Z", "2026-03-15T19:30:00Z"),  # degraded
    ("2026-03-15T22:00:00Z", "2026-03-15T22:30:00Z"),  # degraded
    ("2026-03-16T02:00:00Z", "2026-03-16T02:30:00Z"),
    ("2026-03-16T06:00:00Z", "2026-03-16T06:30:00Z"),
    ("2026-03-16T10:00:00Z", "2026-03-16T10:30:00Z"),
]

TERMINAL_STATUSES = {"completed", "failed", "partial"}


def get_eval_runs(asset_name: str, slo_name: str) -> list[tuple[str, list[int]]]:
    """Return (evaluation_name, window_indices) pairs for this asset."""
    if "laptop" in asset_name:
        return [("load-test", list(range(10)))]
    if "vm-" in asset_name:
        return [
            ("user-experience", list(range(10))),
            ("optimization-testing", [0, 3, 6, 9]),
        ]
    # E-commerce
    return [
        ("load-test", list(range(10))),
        ("prod-validation", [0, 2, 4, 6, 8]),
    ]


def main() -> None:
    """Trigger all evaluations, then poll until every one completes."""
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <api_url>", file=sys.stderr)
        sys.exit(1)

    client = TropekClient(sys.argv[1])
    total = sum(sum(len(indices) for _, indices in get_eval_runs(a, s)) for a, s in ASSETS)
    print(f"Triggering {total} evaluations...")

    eval_ids: list[str] = []
    for asset_name, slo_name in ASSETS:
        runs = get_eval_runs(asset_name, slo_name)
        for eval_name, window_indices in runs:
            for wi in window_indices:
                start, end = WINDOWS[wi]
                result = client.evaluations.trigger(
                    asset_name,
                    eval_name,
                    slo_name,
                    start,
                    end,
                )
                eval_ids.append(result["id"])

    print(f"Triggered {len(eval_ids)}, waiting for completion...")
    pending = set(eval_ids)
    for _ in range(180):
        still_pending: set[str] = set()
        for eid in pending:
            ev = client.evaluations.get(str(eid))
            if ev.status not in TERMINAL_STATUSES:
                still_pending.add(eid)
        pending = still_pending
        done = len(eval_ids) - len(pending)
        print(f"  {done}/{len(eval_ids)} complete...", end="\r", flush=True)
        if not pending:
            break
        time.sleep(2)

    print()
    results = [client.evaluations.get(str(eid)) for eid in eval_ids]
    passed = sum(1 for e in results if e.result == "pass")
    failed = sum(1 for e in results if e.result == "fail")
    warning = sum(1 for e in results if e.result == "warning")
    completed = sum(1 for e in results if e.status == "completed")
    print(
        f"seeded: {completed}/{total} completed — {passed} pass, {warning} warning, {failed} fail"
    )


if __name__ == "__main__":
    main()
