# api/tests/test_qg_router.py
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from tropek.db.session import get_session
from tropek.main import app
from tropek.queue import get_arq_pool


def _make_mock_session():
    """Build an AsyncSession mock whose execute() returns sensible empty results."""
    session = MagicMock()

    # scalar_one() returns 0 (for count queries)
    count_result = MagicMock()
    count_result.scalar_one.return_value = 0

    # scalars().all() returns [] (for list queries)
    rows_result = MagicMock()
    rows_result.scalars.return_value.all.return_value = []

    # execute() alternates: first call → count, subsequent → rows
    execute_results = [count_result, rows_result]
    call_count = {'n': 0}

    async def _execute(query, *args, **kwargs):
        idx = min(call_count['n'], len(execute_results) - 1)
        call_count['n'] += 1
        return execute_results[idx]

    session.execute = _execute
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


async def _mock_session():
    """Override get_session with a no-op async session for unit tests."""
    yield _make_mock_session()


@pytest.fixture
def client():
    mock_pool = AsyncMock()
    app.dependency_overrides[get_session] = _mock_session
    app.dependency_overrides[get_arq_pool] = lambda: mock_pool
    try:
        with patch('tropek.main.create_arq_pool', return_value=mock_pool), TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


def test_trend_rejects_both_eval_id_and_asset_name(client):
    resp = client.get(
        '/trend',
        params={
            'eval_id': str(uuid.uuid4()),
            'asset_name': 'vm-01',
            'slo_name': 'my-slo',
            'metric': 'cpu',
        },
    )
    assert resp.status_code == 422


def test_trend_rejects_neither_eval_id_nor_asset_name(client):
    resp = client.get('/trend', params={'metric': 'cpu'})
    assert resp.status_code == 422


def test_trend_rejects_eval_id_combined_with_asset_name(client):
    resp = client.get(
        '/trend',
        params={
            'eval_id': str(uuid.uuid4()),
            'asset_name': 'vm-01',
            'metric': 'cpu',
        },
    )
    assert resp.status_code == 422


def test_trend_rejects_asset_name_without_slo_name(client):
    resp = client.get(
        '/trend',
        params={'asset_name': 'vm-01', 'metric': 'cpu'},
    )
    assert resp.status_code == 422


def test_evaluations_rejects_date_with_from(client):
    resp = client.get(
        '/evaluations',
        params={'date': '2026-03-01', 'from': '2026-03-01T00:00:00Z'},
    )
    assert resp.status_code == 422


def test_evaluations_rejects_date_with_to(client):
    resp = client.get(
        '/evaluations',
        params={'date': '2026-03-01', 'to': '2026-03-01T23:59:59Z'},
    )
    assert resp.status_code == 422


def test_evaluations_accepts_from_to_without_date(client):
    resp = client.get(
        '/evaluations',
        params={'from': '2026-03-01T00:00:00Z', 'to': '2026-03-01T23:59:59Z'},
    )
    # Should be 200 (empty results) — NOT 422 (validation error)
    assert resp.status_code == 200
