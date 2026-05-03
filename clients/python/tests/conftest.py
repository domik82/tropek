"""Shared fixtures and constants for client tests."""

import json
from pathlib import Path

import pytest
from tropek_client import TropekClient

BASE_URL = 'http://test-api:8080'

UUID1 = '00000000-0000-0000-0000-000000000001'
UUID2 = '00000000-0000-0000-0000-000000000002'
TIMESTAMP = '2026-03-01T00:00:00Z'

FIXTURES_DIR = Path(__file__).parent / 'fixtures' / 'api_responses'


def load_fixture(name: str) -> dict | list:
    """Load a JSON fixture file by name (without .json extension)."""
    path = FIXTURES_DIR / f'{name}.json'
    if not path.exists():
        pytest.skip(f'fixture {name}.json not found — run capture_responses.py first')
    return json.loads(path.read_text())


@pytest.fixture
def client():
    return TropekClient(base_url=BASE_URL)
