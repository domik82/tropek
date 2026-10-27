"""Integration tests for POST /evaluations and POST /evaluations/batch.

Requires TEST_DATABASE_URL and a running TimescaleDB instance.
Run: uv run pytest api/tests/db/test_trigger_evaluate.py -m integration -v
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from tropek.db.session import get_session
from tropek.main import app
from tropek.queue import get_arq_pool


@pytest_asyncio.fixture()
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    """Yield an httpx AsyncClient bound to the FastAPI app with test DB session."""

    async def _override_session() -> AsyncGenerator[AsyncSession]:
        yield db_session

    mock_pool = AsyncMock()
    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[get_arq_pool] = lambda: mock_pool
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture()
async def seeded_asset_with_slo_binding(async_client: AsyncClient) -> tuple[str, list[str]]:
    """Seed one asset with one SLO binding via the HTTP API. Returns (asset_name, [slo_name])."""
    suffix = uuid.uuid4().hex[:8]

    type_name = f'vm-eval-{suffix}'
    resp = await async_client.post('/asset-types', json={'name': type_name})
    assert resp.status_code == 201

    asset_name = f'test-asset-{suffix}'
    resp = await async_client.post('/assets', json={'name': asset_name, 'type_name': type_name})
    assert resp.status_code == 201

    ds_name = f'ds-{suffix}'
    resp = await async_client.post(
        '/datasources',
        json={
            'name': ds_name,
            'adapter_type': 'mock',
            'adapter_url': 'http://mock:8082',
        },
    )
    assert resp.status_code == 201

    sli_name = f'sli-{suffix}'
    resp = await async_client.post(
        '/sli-definitions',
        json={
            'name': sli_name,
            'adapter_type': 'mock',
            'indicators': {'metric_value': 'mock_query'},
        },
    )
    assert resp.status_code == 201

    slo_name = f'slo-{suffix}'
    resp = await async_client.post(
        '/slo-definitions',
        json={
            'name': slo_name,
            'sli_name': sli_name,
            'sli_version': 1,
            'total_score_pass_threshold': 90.0,
            'total_score_warning_threshold': 75.0,
            'objectives': [{'sli': 'metric_value', 'pass_threshold': ['<100']}],
        },
    )
    assert resp.status_code == 201
    slo_def_id = resp.json()['id']

    resp = await async_client.put(
        f'/assets/{asset_name}/slo-definitions/{slo_def_id}',
        json={'data_source_name': ds_name},
    )
    assert resp.status_code == 200

    return asset_name, [slo_name]


@pytest.mark.integration
async def test_evaluate_single_creates_run_and_children(
    async_client: AsyncClient,
    seeded_asset_with_slo_binding: tuple[str, list[str]],
) -> None:
    """POST /evaluations creates one EvaluationRun + one SLOEvaluation per bound SLO."""
    asset_name, slo_names = seeded_asset_with_slo_binding

    resp = await async_client.post(
        '/evaluations',
        json={
            'asset_name': asset_name,
            'eval_name': 'ci-check',
            'period_start': '2026-01-15T00:00:00Z',
            'period_end': '2026-01-15T23:59:59Z',
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert 'evaluation_id' in body
    assert len(body['slo_evaluation_ids']) == len(slo_names)


@pytest.mark.integration
async def test_evaluate_batch_by_date(
    async_client: AsyncClient,
    seeded_asset_with_slo_binding: tuple[str, list[str]],
) -> None:
    """POST /evaluations/batch with mode=by_date creates one run per period."""
    asset_name, _ = seeded_asset_with_slo_binding

    resp = await async_client.post(
        '/evaluations/batch',
        json={
            'mode': 'by_date',
            'asset_name': asset_name,
            'eval_name': 'daily',
            'periods': [
                {'period_start': '2026-01-15T00:00:00Z', 'period_end': '2026-01-15T23:59:59Z'},
                {'period_start': '2026-01-16T00:00:00Z', 'period_end': '2026-01-16T23:59:59Z'},
            ],
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert len(body['evaluation_ids']) == 2


@pytest.mark.integration
async def test_evaluate_unknown_asset_returns_404(async_client: AsyncClient) -> None:
    """POST /evaluations with unknown asset_name returns 404."""
    resp = await async_client.post(
        '/evaluations',
        json={
            'asset_name': 'no-such-asset',
            'eval_name': 'test',
            'period_start': '2026-01-15T00:00:00Z',
            'period_end': '2026-01-15T23:59:59Z',
        },
    )
    assert resp.status_code == 404
