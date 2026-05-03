"""Shared fixtures and constants for client tests."""

import json
from pathlib import Path

import pytest
from tropek_client import TropekClient

BASE_URL = 'http://test-api:8080'

UUID1 = '00000000-0000-0000-0000-000000000001'
UUID2 = '00000000-0000-0000-0000-000000000002'
TIMESTAMP = '2026-03-01T00:00:00Z'

TESTS_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = TESTS_DIR / 'fixtures' / 'api_responses'


def find_workspace_root() -> Path:
    """Walk up from this file until we find the workspace-level pyproject.toml.

    Only needed by monorepo-specific tests (e.g. API contract drift).
    Raises FileNotFoundError when run outside the monorepo (e.g. PyPI install).
    """
    current = TESTS_DIR
    while current != current.parent:
        candidate = current / 'pyproject.toml'
        if candidate.exists() and '[tool.uv.workspace]' in candidate.read_text():
            return current
        current = current.parent
    raise FileNotFoundError('could not find workspace root (pyproject.toml with [tool.uv.workspace])')


def load_fixture(name: str) -> dict | list:
    """Load a JSON fixture file by name (without .json extension)."""
    path = FIXTURES_DIR / f'{name}.json'
    if not path.exists():
        pytest.skip(f'fixture {name}.json not found — run capture_responses.py first')
    return json.loads(path.read_text())


@pytest.fixture
def client():
    return TropekClient(base_url=BASE_URL)
