"""Apply bootstrap manifests to a running TROPEK API.

Usage: uv run --directory clients/python python ../../scripts/bootstrap.py <api_url>
"""

from __future__ import annotations

import sys
from pathlib import Path

from tropek_client import TropekClient
from tropek_client.manifest import apply, load_manifests

MANIFESTS_DIR = Path(__file__).resolve().parent.parent / 'bootstrap_mock' / 'manifests'


def main() -> None:
    """Apply bootstrap manifests and report counts."""
    if len(sys.argv) != 2:  # noqa: PLR2004
        print(f'usage: {sys.argv[0]} <api_url>', file=sys.stderr)
        sys.exit(1)

    client = TropekClient(sys.argv[1])
    docs = load_manifests(str(MANIFESTS_DIR))
    result = apply(client, docs)
    print(f'bootstrap: {result.created} created, {result.updated} updated, {result.skipped} skipped')
    if result.failed:
        raise RuntimeError(f'bootstrap failed: {result.errors}')


if __name__ == '__main__':
    main()
