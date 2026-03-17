"""Seed historical evaluation data for visual inspection.

Triggers 40 evaluations (4 assets x 10 time windows) spread across
48 hours of mock data. Two windows fall in the degraded period
(2026-03-15T18:00Z - 2026-03-16T00:00Z) to produce failures.

Evaluations are triggered sequentially (one at a time) to avoid
TimescaleDB deadlocks caused by concurrent chunk-creation when arq
runs multiple jobs in parallel.

Usage: uv run --directory clients/python python ../../scripts/seed_evaluations.py <api_url>
"""

from __future__ import annotations

import sys
import time

from tropek_client import TropekClient

# (asset_name, slo_name) pairs matching the bootstrap SLO links
ASSETS = [
    ("checkout-api", "http-availability-slo"),
    ("product-catalog", "http-availability-slo"),
    ("user-service", "http-availability-slo"),
    ("orders-db", "db-performance-slo"),
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


def _wait(client: TropekClient, eval_id: str, timeout: int = 60) -> object:
    """Poll a single evaluation until it reaches a terminal status."""
    for _ in range(timeout):
        ev = client.evaluations.get(eval_id)
        if ev.status in TERMINAL_STATUSES:
            return ev
        time.sleep(1)
    raise TimeoutError(f"evaluation {eval_id} did not complete within {timeout}s")


def main() -> None:
    """Trigger evaluations one at a time and report results."""
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <api_url>", file=sys.stderr)
        sys.exit(1)

    client = TropekClient(sys.argv[1])
    total = len(ASSETS) * len(WINDOWS)
    results = []

    for asset_idx, (asset_name, slo_name) in enumerate(ASSETS):
        for window_idx, (start, end) in enumerate(WINDOWS):
            n = asset_idx * len(WINDOWS) + window_idx + 1
            print(f"  [{n}/{total}] {asset_name}  {start[:13]}...", end=" ", flush=True)

            triggered = client.evaluations.trigger(
                asset_name,
                f"seed-{asset_idx}-{window_idx}",
                slo_name,
                start,
                end,
            )
            ev = _wait(client, triggered["id"])
            results.append(ev)
            print(ev.result or ev.status)

    passed = sum(1 for e in results if e.result == "pass")
    failed = sum(1 for e in results if e.result == "fail")
    warning = sum(1 for e in results if e.result == "warning")
    completed = sum(1 for e in results if e.status == "completed")
    print(
        f"\nseeded: {completed}/{total} completed — {passed} pass, {warning} warning, {failed} fail"
    )


if __name__ == "__main__":
    main()
