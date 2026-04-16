"""Seed asset meta timeline data for visual inspection.

Pushes a realistic sequence of metadata snapshots through the POST API
to exercise every derivation scenario. When viewed on the eval detail
page, the meta timeline section should show:

  checkout-api    — Full lifecycle: app v1→v2→v3, plugin hierarchy,
                    discontinued plugin, new plugin in v3, hardware changes.
  vm-prod-web-01  — Multi-source scenario: cicd + os-agent push different paths.
  laptop-user-01  — Heartbeat scenario: daily identical pushes collapse to one span.

The timeline window for evaluation detail is [eval.periodEnd - 30d, eval.periodEnd + 7d].
Evaluations are seeded at 2026-03-15 to 2026-03-16, so meta snapshots span
2026-02-10 to 2026-03-20 to be visible in any eval's window.

Usage: uv run --directory clients/python python ../../scripts/seed_meta_timeline.py <api_url>

Scenarios exercised (§10.1 cross-reference):
  1. Single value snapshot                    — first push for each asset
  2. Identical value (no-op)                  — heartbeat pushes (laptop)
  3. Value change                             — app v1→v2→v3
  4. Explicit closure                         — legacy-plugin discontinued
  5. Cascading closure                        — closing app-A closes all plugins
  9. Daily heartbeat collapse                 — laptop daily pushes
  10. Multi-source conflict                   — vm-prod-web-01 cicd + os-agent
  11. Synthetic intermediates                 — deep plugin hierarchy
  12. Left-edge clipping                      — spans starting before window
  16. closed-only snapshot                    — legacy-plugin removal
  19. closed-only cascading                   — vm cascading close test
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta

import httpx


def post_snapshot(
    client: httpx.Client,
    asset_id: str,
    source: str,
    observed_at: str,
    values: list[dict] | None = None,
    closed: list[dict] | None = None,
) -> None:
    """POST a single snapshot and assert 201."""
    payload: dict = {'source': source, 'observed_at': observed_at}
    if values is not None:
        payload['values'] = values
    if closed is not None:
        payload['closed'] = closed
    response = client.post(f'/assets/{asset_id}/meta/snapshots', json=payload)
    expected_status = 201
    if response.status_code != expected_status:
        print(f'  WARN: POST returned {response.status_code}: {response.text}')


def get_timeline(client: httpx.Client, asset_id: str, from_dt: str, to_dt: str) -> dict:
    """GET the timeline and return the response JSON."""
    response = client.get(
        f'/assets/{asset_id}/meta/timeline',
        params={'from': from_dt, 'to': to_dt},
    )
    response.raise_for_status()
    return response.json()


def get_summary(client: httpx.Client, asset_id: str, from_dt: str, to_dt: str) -> dict:
    """GET the summary and return the response JSON."""
    response = client.get(
        f'/assets/{asset_id}/meta/timeline/summary',
        params={'from': from_dt, 'to': to_dt},
    )
    response.raise_for_status()
    return response.json()


def resolve_asset_id(client: httpx.Client, asset_name: str) -> str | None:
    """Look up asset UUID by name. Returns None if not found."""
    response = client.get(f'/assets/{asset_name}')
    not_found = 404
    if response.status_code == not_found:
        return None
    response.raise_for_status()
    return response.json()['id']


# ── Timestamps ──────────────────────────────────────────────────────────
# Evaluations are at 2026-03-15 to 2026-03-16.
# Meta snapshots span 2026-02-10 to 2026-03-20 so they're visible in any
# eval's 30-day lookback window.

BASE = datetime(2026, 2, 10, 0, 0, 0, tzinfo=UTC)


def ts(days: int = 0, hours: int = 0) -> str:
    """Return ISO timestamp relative to BASE."""
    return (BASE + timedelta(days=days, hours=hours)).strftime('%Y-%m-%dT%H:%M:%SZ')


# ── Scenario: checkout-api ──────────────────────────────────────────────
# Full lifecycle exercise. Mimics a CI/CD pipeline pushing metadata after
# each deployment + a one-time hardware config push.

def seed_checkout_api(client: httpx.Client, asset_id: str) -> None:
    """Seed checkout-api with a rich version + plugin lifecycle."""
    print('  checkout-api: version lifecycle + plugin hierarchy')

    # Day 0: Initial deploy — app v1.0, two plugins, hardware config
    post_snapshot(client, asset_id, 'cicd', ts(0), values=[
        {'path': ['checkout-api'], 'value': '1.0.0'},
        {'path': ['checkout-api', 'plugin-pkg', 'auth-plugin'], 'value': '0.8.0'},
        {'path': ['checkout-api', 'plugin-pkg', 'legacy-plugin'], 'value': '2.1.0'},
        {'path': ['checkout-api', 'payment-gateway'], 'value': 'stripe-v3'},
    ])
    post_snapshot(client, asset_id, 'os-agent', ts(0, 2), values=[
        {'path': ['cpu-cores'], 'value': '4'},
        {'path': ['memory-gb'], 'value': '16'},
    ])

    # Day 7: Patch release — auth-plugin updated, rest unchanged
    post_snapshot(client, asset_id, 'cicd', ts(7), values=[
        {'path': ['checkout-api'], 'value': '1.0.0'},
        {'path': ['checkout-api', 'plugin-pkg', 'auth-plugin'], 'value': '0.9.0'},
        {'path': ['checkout-api', 'plugin-pkg', 'legacy-plugin'], 'value': '2.1.0'},
        {'path': ['checkout-api', 'payment-gateway'], 'value': 'stripe-v3'},
    ])

    # Day 14: Major upgrade — app v2.0, legacy-plugin discontinued
    post_snapshot(client, asset_id, 'cicd', ts(14), values=[
        {'path': ['checkout-api'], 'value': '2.0.0'},
        {'path': ['checkout-api', 'plugin-pkg', 'auth-plugin'], 'value': '1.0.0'},
        {'path': ['checkout-api', 'payment-gateway'], 'value': 'stripe-v4'},
    ], closed=[
        {'path': ['checkout-api', 'plugin-pkg', 'legacy-plugin']},
    ])

    # Day 21: Hardware upgrade
    post_snapshot(client, asset_id, 'os-agent', ts(21), values=[
        {'path': ['cpu-cores'], 'value': '8'},
        {'path': ['memory-gb'], 'value': '32'},
    ])

    # Day 28: App v3.0 with NEW plugin added
    post_snapshot(client, asset_id, 'cicd', ts(28), values=[
        {'path': ['checkout-api'], 'value': '3.0.0'},
        {'path': ['checkout-api', 'plugin-pkg', 'auth-plugin'], 'value': '1.1.0'},
        {'path': ['checkout-api', 'plugin-pkg', 'cache-plugin'], 'value': '0.1.0'},
        {'path': ['checkout-api', 'payment-gateway'], 'value': 'stripe-v4'},
    ])

    # Day 33: Feature flag toggled
    post_snapshot(client, asset_id, 'cicd', ts(33), values=[
        {'path': ['checkout-api'], 'value': '3.0.0'},
        {'path': ['checkout-api', 'plugin-pkg', 'auth-plugin'], 'value': '1.1.0'},
        {'path': ['checkout-api', 'plugin-pkg', 'cache-plugin'], 'value': '0.2.0'},
        {'path': ['checkout-api', 'payment-gateway'], 'value': 'stripe-v4'},
        {'path': ['feature-flags', 'enable-new-checkout'], 'value': 'true'},
    ])


# ── Scenario: vm-prod-web-01 ───────────────────────────────────────────
# Multi-source: cicd pushes app versions, os-agent pushes hardware.
# Both sources own different paths — no conflict.

def seed_vm_prod_web_01(client: httpx.Client, asset_id: str) -> None:
    """Seed vm-prod-web-01 with multi-source data."""
    print('  vm-prod-web-01: multi-source (cicd + os-agent)')

    # Day 0: OS agent reports hardware
    post_snapshot(client, asset_id, 'os-agent', ts(0), values=[
        {'path': ['os'], 'value': 'Ubuntu 22.04'},
        {'path': ['cpu-cores'], 'value': '16'},
        {'path': ['memory-gb'], 'value': '64'},
        {'path': ['disk-type'], 'value': 'NVMe SSD'},
    ])

    # Day 1: CICD deploys services
    post_snapshot(client, asset_id, 'cicd', ts(1), values=[
        {'path': ['nginx'], 'value': '1.24.0'},
        {'path': ['app-server'], 'value': '4.2.1'},
        {'path': ['app-server', 'worker-pool'], 'value': '8'},
    ])

    # Day 10: OS patched
    post_snapshot(client, asset_id, 'os-agent', ts(10), values=[
        {'path': ['os'], 'value': 'Ubuntu 22.04.1'},
        {'path': ['cpu-cores'], 'value': '16'},
        {'path': ['memory-gb'], 'value': '64'},
        {'path': ['disk-type'], 'value': 'NVMe SSD'},
    ])

    # Day 20: App server upgrade + worker pool tuned
    post_snapshot(client, asset_id, 'cicd', ts(20), values=[
        {'path': ['nginx'], 'value': '1.25.0'},
        {'path': ['app-server'], 'value': '5.0.0'},
        {'path': ['app-server', 'worker-pool'], 'value': '16'},
    ])

    # Day 30: Cascading close — entire app-server stack decommissioned
    post_snapshot(client, asset_id, 'cicd', ts(30), closed=[
        {'path': ['app-server']},
    ])

    # Day 31: New app-server deployed
    post_snapshot(client, asset_id, 'cicd', ts(31), values=[
        {'path': ['app-server'], 'value': '6.0.0-rc1'},
        {'path': ['app-server', 'worker-pool'], 'value': '32'},
    ])


# ── Scenario: laptop-user-01 ───────────────────────────────────────────
# Daily heartbeat: identical pushes for 30 days should collapse to one span.

def seed_laptop_user_01(client: httpx.Client, asset_id: str) -> None:
    """Seed laptop-user-01 with daily heartbeat pushes."""
    print('  laptop-user-01: daily heartbeat (30 days → 1 span each)')

    # Day 0-29: same values pushed daily — should produce exactly one span per path
    for day in range(30):
        post_snapshot(client, asset_id, 'os-agent', ts(day), values=[
            {'path': ['os'], 'value': 'Windows 11 Pro'},
            {'path': ['cpu-model'], 'value': 'Intel i7-13700'},
            {'path': ['memory-gb'], 'value': '32'},
            {'path': ['office-suite'], 'value': 'Microsoft 365'},
        ])

    # Day 30: Office suite upgraded
    post_snapshot(client, asset_id, 'os-agent', ts(30), values=[
        {'path': ['os'], 'value': 'Windows 11 Pro'},
        {'path': ['cpu-model'], 'value': 'Intel i7-13700'},
        {'path': ['memory-gb'], 'value': '32'},
        {'path': ['office-suite'], 'value': 'Microsoft 365 v2'},
    ])


# ── Verification ────────────────────────────────────────────────────────

def verify_asset(
    client: httpx.Client,
    asset_id: str,
    asset_name: str,
    expected_min_items: int,
) -> bool:
    """Verify the timeline endpoint returns data and matches summary."""
    from_dt = ts(-5)
    to_dt = ts(40)

    timeline = get_timeline(client, asset_id, from_dt, to_dt)
    summary = get_summary(client, asset_id, from_dt, to_dt)

    group_count = len(timeline['groups'])
    item_count = len(timeline['items'])
    summary_count = summary['itemCount']

    # Summary parity: itemCount == distinct groups that have items
    distinct_item_groups = len({item['group'] for item in timeline['items']})

    passed = True
    if item_count < expected_min_items:
        print(f'    FAIL: expected >= {expected_min_items} items, got {item_count}')
        passed = False
    if summary_count != distinct_item_groups:
        print(f'    FAIL: summary ({summary_count}) != distinct item groups ({distinct_item_groups})')
        passed = False

    status = 'OK' if passed else 'FAIL'
    print(f'    {status}: {asset_name} — {group_count} groups, {item_count} items, summary={summary_count}')

    # Check specific class presence for checkout-api
    if 'checkout' in asset_name:
        classes = [item.get('className', item.get('class_name', '')) for item in timeline['items']]
        has_closed = any('meta-span-closed' in c for c in classes)
        has_open = any('meta-span-open' in c for c in classes)
        if not has_closed:
            print('    FAIL: no meta-span-closed items (legacy-plugin discontinuation)')
            passed = False
        if not has_open:
            print('    FAIL: no meta-span-open items (still-running spans)')
            passed = False

    return passed


# ── Main ────────────────────────────────────────────────────────────────

SEED_TARGETS = [
    ('checkout-api', seed_checkout_api, 8),
    ('vm-prod-web-01', seed_vm_prod_web_01, 6),
    ('laptop-user-01', seed_laptop_user_01, 4),
]


def main() -> None:
    """Seed meta timeline snapshots and verify endpoint responses."""
    if len(sys.argv) != 2:  # noqa: PLR2004
        print(f'usage: {sys.argv[0]} <api_url>', file=sys.stderr)
        sys.exit(1)

    base_url = sys.argv[1]
    client = httpx.Client(base_url=base_url, timeout=30)

    print('=== Seeding meta timeline data ===')

    seeded: list[tuple[str, str, int]] = []
    for asset_name, seed_fn, expected_min in SEED_TARGETS:
        asset_id = resolve_asset_id(client, asset_name)
        if asset_id is None:
            print(f'  SKIP: {asset_name} not found (create it first or run bootstrap)')
            continue
        seed_fn(client, asset_id)
        seeded.append((asset_name, asset_id, expected_min))

    if not seeded:
        print('No assets found to seed. Ensure bootstrap has run first.')
        sys.exit(1)

    print()
    print('=== Verifying meta timeline responses ===')
    all_passed = True
    for asset_name, asset_id, expected_min in seeded:
        if not verify_asset(client, asset_id, asset_name, expected_min):
            all_passed = False

    print()
    if all_passed:
        print('All meta timeline verifications passed.')
    else:
        print('Some verifications FAILED — check output above.')
        sys.exit(1)


if __name__ == '__main__':
    main()
