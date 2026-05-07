"""Run dev-setup stages sequentially against a live TROPEK API.

Each stage is a standalone script in dev_setup/stages/. Stages can be run
individually or all together. The orchestrator provides clear per-stage
error reporting and timing.

Usage:
    uv run --directory clients/python python ../../dev_setup/run.py <api_url> [options] [stage...]

Examples:
    # Run all stages (default)
    uv run --directory clients/python python ../../dev_setup/run.py http://localhost:9080

    # Run specific stages
    uv run --directory clients/python python ../../dev_setup/run.py http://localhost:9080 bootstrap seed-evaluations

    # Docker mode — rewrite adapter URLs in manifests for docker-internal networking
    uv run --directory clients/python python ../../dev_setup/run.py http://localhost:8080
        --adapter-url http://adapter-mock:8082

    # List available stages
    uv run --directory clients/python python ../../dev_setup/run.py --list

Available stages:
    bootstrap           Apply mock bootstrap manifests
    seed-evaluations    Seed 48h of historical evaluation data
    seed-meta           Seed asset meta timeline data
    e2e-tests           Run end-to-end integration tests
    smoke-tests         Smoke test every client route
    capture-fixtures    Capture API responses as test fixtures
    prometheus-bootstrap Apply Prometheus bootstrap manifests (requires adapter)
    seed-prometheus     Seed Prometheus evaluation data (requires adapter)
"""

from __future__ import annotations

import importlib
import os
import sys
import time
from pathlib import Path

from tropek_client import TropekClient
from tropek_client.manifest import apply, load_manifests

DEV_SETUP_DIR = Path(__file__).resolve().parent
STAGES_DIR = DEV_SETUP_DIR / 'stages'
PROMETHEUS_DIR = DEV_SETUP_DIR / 'prometheus'

STAGE_REGISTRY: list[tuple[str, str, str]] = [
    ('bootstrap', 'bootstrap', 'Apply mock bootstrap manifests'),
    ('seed-evaluations', 'seed_evaluations', 'Seed 48h of historical evaluation data'),
    ('seed-meta', 'seed_meta_timeline', 'Seed asset meta timeline data'),
    ('e2e-tests', 'e2e_tests', 'Run end-to-end integration tests'),
    ('smoke-tests', 'smoke_test_routes', 'Smoke test every client route'),
    ('capture-fixtures', 'capture_responses', 'Capture API responses as test fixtures'),
    ('prometheus-bootstrap', '_prometheus_bootstrap', 'Apply Prometheus bootstrap manifests'),
    ('seed-prometheus', 'seed_e2e_prometheus', 'Seed Prometheus evaluation data'),
]

DEFAULT_STAGES = [
    'bootstrap',
    'seed-evaluations',
    'seed-meta',
    'e2e-tests',
    'smoke-tests',
]

MIN_REQUIRED_ARGS = 2


def _rewrite_adapter_urls(docs: list, adapter_url: str) -> None:
    """Rewrite adapter_url in all DataSource manifests (in-place)."""
    for doc in docs:
        if doc.kind == 'DataSource' and 'adapter_url' in doc.spec:
            doc.spec['adapter_url'] = adapter_url


def _run_stage_module(module_name: str, api_url: str) -> None:
    """Run a stage by importing and calling its main()."""
    module_path = STAGES_DIR / f'{module_name}.py'
    if not module_path.exists():
        raise FileNotFoundError(f'stage module not found: {module_path}')
    original_argv = sys.argv
    stages_str = str(STAGES_DIR)
    sys.argv = [str(module_path), api_url]
    if stages_str not in sys.path:
        sys.path.insert(0, stages_str)
    try:
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        module.main()
    finally:
        sys.argv = original_argv
        sys.modules.pop(module_name, None)


def _bootstrap_with_override(api_url: str, manifests_dir: Path, adapter_url: str | None) -> None:
    """Apply manifests, optionally rewriting adapter URLs."""
    client = TropekClient(api_url)
    docs = load_manifests(str(manifests_dir))
    if adapter_url:
        _rewrite_adapter_urls(docs, adapter_url)
    result = apply(client, docs)
    label = 'prometheus bootstrap' if manifests_dir == PROMETHEUS_DIR else 'bootstrap'
    print(f'{label}: {result.created} created, {result.updated} updated, {result.skipped} skipped')
    if result.failed:
        raise RuntimeError(f'{label} failed: {result.errors}')


def run_stage(stage_name: str, api_url: str, adapter_url: str | None = None) -> bool:
    """Run a single stage, return True on success."""
    registry_entry = next((entry for entry in STAGE_REGISTRY if entry[0] == stage_name), None)
    if registry_entry is None:
        print(f'  ERROR  unknown stage: {stage_name}')
        return False

    label, module_name, description = registry_entry
    print(f'\n{"=" * 60}')
    print(f'  STAGE: {label} — {description}')
    print(f'{"=" * 60}')

    mock_dir = DEV_SETUP_DIR / 'mock'
    start = time.time()
    try:
        if module_name == 'bootstrap':
            _bootstrap_with_override(api_url, mock_dir, adapter_url)
        elif module_name == '_prometheus_bootstrap':
            _bootstrap_with_override(api_url, PROMETHEUS_DIR, adapter_url)
        else:
            _run_stage_module(module_name, api_url)
        elapsed = time.time() - start
        print(f'\n  OK  {label} ({elapsed:.1f}s)')
        return True
    except (RuntimeError, FileNotFoundError, ImportError, AttributeError, SystemExit) as exc:
        elapsed = time.time() - start
        print(f'\n  FAILED  {label} ({elapsed:.1f}s): {exc}')
        return False


def _list_stages() -> None:
    """Print available stages and exit."""
    print('Available stages:')
    for name, _, description in STAGE_REGISTRY:
        default_marker = ' (default)' if name in DEFAULT_STAGES else ''
        print(f'  {name:24s} {description}{default_marker}')


def _parse_args() -> tuple[str, str | None, list[str]]:
    """Parse CLI args, return (api_url, adapter_url, stages). Exits on invalid input."""
    args = sys.argv[1:]
    adapter_url = None

    filtered = []
    skip_next = False
    for i, arg in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if arg == '--adapter-url':
            if i + 1 >= len(args):
                print('error: --adapter-url requires a value', file=sys.stderr)
                sys.exit(1)
            adapter_url = args[i + 1]
            skip_next = True
        elif arg.startswith('--adapter-url='):
            adapter_url = arg.split('=', 1)[1]
        else:
            filtered.append(arg)

    if len(filtered) < 1:
        print(f'usage: {sys.argv[0]} <api_url> [--adapter-url URL] [stage...]')
        print(f'       {sys.argv[0]} --list')
        sys.exit(1)

    api_url = filtered[0]
    requested = filtered[1:] or list(DEFAULT_STAGES)

    adapter_url = adapter_url or os.environ.get('TROPEK_ADAPTER_URL')

    valid_names = {entry[0] for entry in STAGE_REGISTRY}
    for stage_name in requested:
        if stage_name not in valid_names:
            print(f'error: unknown stage "{stage_name}"')
            print(f'available: {", ".join(valid_names)}')
            sys.exit(1)

    return api_url, adapter_url, requested


def _print_summary(
    results: list[tuple[str, bool]],
    requested_stages: list[str],
    overall_elapsed: float,
) -> None:
    """Print the run summary."""
    print(f'\n{"=" * 60}')
    print(f'  SUMMARY ({overall_elapsed:.1f}s total)')
    print(f'{"=" * 60}')
    for name, success in results:
        status = 'OK' if success else 'FAILED'
        print(f'  {status:8s} {name}')

    executed = {r[0] for r in results}
    for name in requested_stages:
        if name not in executed:
            print(f'  {"SKIPPED":8s} {name}')


def main() -> None:
    """Parse args and run requested stages."""
    if '--list' in sys.argv:
        _list_stages()
        return

    api_url, adapter_url, requested_stages = _parse_args()

    if adapter_url:
        print(f'  adapter URL override: {adapter_url}')

    results: list[tuple[str, bool]] = []
    overall_start = time.time()

    for stage_name in requested_stages:
        success = run_stage(stage_name, api_url, adapter_url)
        results.append((stage_name, success))
        if not success:
            print(f'\nStopping — stage "{stage_name}" failed.')
            break

    _print_summary(results, requested_stages, time.time() - overall_start)

    if any(not success for _, success in results):
        sys.exit(1)


if __name__ == '__main__':
    main()
