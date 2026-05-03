"""Apply bootstrap manifests to a running TROPEK API.

Usage: uv run --directory clients/python python ../../dev_setup/stages/bootstrap.py <api_url>
"""

from __future__ import annotations

import sys

from _paths import PROJECT_ROOT
from tropek_client import TropekClient
from tropek_client.manifest import apply, load_manifests

MANIFESTS_DIR = PROJECT_ROOT / 'dev_setup' / 'mock'


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
