"""Integration tests for SLO binding resolution across all 4 assignment paths.

Tests go through the HTTP layer to verify end-to-end binding discovery.
Each test creates isolated entities with a shared prefix for readability.

Requires TEST_DATABASE_URL and a running TimescaleDB instance.
Run: ./scripts/api-test.sh --tail 20 tests/db/test_binding_resolution.py -v -m integration
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from app.db.session import get_session
from app.main import app
from app.queue import get_arq_pool
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


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


@pytest.fixture
def prefix() -> str:
    """Short random prefix for test entity names to avoid cross-test collisions."""
    return uuid.uuid4().hex[:6]


async def _create_base_entities(
    client: AsyncClient, prefix: str,
) -> tuple[str, str, str]:
    """Create asset type, datasource, and SLI shared across binding tests.

    Returns (type_name, ds_name, sli_name).
    """
    type_name = f'{prefix}-svc'
    resp = await client.post('/asset-types', json={'name': type_name})
    assert resp.status_code == 201

    ds_name = f'{prefix}-ds'
    resp = await client.post(
        '/datasources',
        json={'name': ds_name, 'adapter_type': 'mock', 'adapter_url': 'http://mock:8082'},
    )
    assert resp.status_code == 201

    sli_name = f'{prefix}-sli'
    resp = await client.post(
        '/sli-definitions',
        json={
            'name': sli_name,
            'adapter_type': 'mock',
            'indicators': {'metric_a': 'mock_query_a'},
        },
    )
    assert resp.status_code == 201

    return type_name, ds_name, sli_name


async def _create_slo(
    client: AsyncClient, slo_name: str, sli_name: str, kind: str = 'standard',
    variables: dict | None = None,
) -> str:
    """Create an SLO definition and return its ID."""
    body: dict = {
        'name': slo_name,
        'sli_name': sli_name,
        'sli_version': 1,
        'total_score_pass_threshold': 90.0,
        'total_score_warning_threshold': 75.0,
        'objectives': [{'sli': 'metric_a', 'pass_threshold': ['<100']}],
    }
    if kind != 'standard':
        body['kind'] = kind
    if variables:
        body['variables'] = variables
    resp = await client.post('/slo-definitions', json=body)
    assert resp.status_code == 201
    return resp.json()['id']


async def _create_asset(client: AsyncClient, name: str, type_name: str) -> None:
    """Create an asset."""
    resp = await client.post('/assets', json={'name': name, 'type_name': type_name})
    assert resp.status_code == 201


async def _create_group_with_member(
    client: AsyncClient, group_name: str, asset_name: str,
) -> None:
    """Create an asset group and add one member."""
    resp = await client.post('/asset-groups', json={'name': group_name})
    assert resp.status_code == 201
    resp = await client.get(f'/assets/{asset_name}')
    assert resp.status_code == 200
    asset_id = resp.json()['id']
    resp = await client.post(
        f'/asset-groups/{group_name}/members',
        json={'asset_id': asset_id, 'weight': 1.0},
    )
    assert resp.status_code == 201


async def _evaluate(client: AsyncClient, asset_name: str) -> tuple[int, dict]:
    """Trigger evaluation and return (status_code, response_body)."""
    resp = await client.post(
        '/evaluate',
        json={
            'asset_name': asset_name,
            'eval_name': 'binding-test',
            'period_start': '2026-01-15T00:00:00Z',
            'period_end': '2026-01-15T23:59:59Z',
        },
    )
    return resp.status_code, resp.json()


# ---------------------------------------------------------------------------
# Test: Direct asset -> SLO assignment
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_evaluate_direct_slo_assignment(
    async_client: AsyncClient, prefix: str,
) -> None:
    """Asset with direct SLO assignment — evaluation discovers the SLO."""
    type_name, ds_name, sli_name = await _create_base_entities(async_client, prefix)

    asset_name = f'{prefix}-direct-slo'
    await _create_asset(async_client, asset_name, type_name)

    slo_name = f'{prefix}-direct-health'
    slo_id = await _create_slo(async_client, slo_name, sli_name)

    resp = await async_client.post(
        f'/assets/{asset_name}/slo-assignments',
        json={'slo_definition_id': slo_id, 'data_source_name': ds_name},
    )
    assert resp.status_code == 201

    status, body = await _evaluate(async_client, asset_name)

    assert status == 201
    assert len(body['slo_evaluation_ids']) == 1


# ---------------------------------------------------------------------------
# Test: Group -> SLO assignment (asset inherits from group)
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_evaluate_group_slo_assignment(
    async_client: AsyncClient, prefix: str,
) -> None:
    """Asset in group — SLO assigned to group is discovered for the asset."""
    type_name, ds_name, sli_name = await _create_base_entities(async_client, prefix)

    asset_name = f'{prefix}-group-slo'
    await _create_asset(async_client, asset_name, type_name)

    group_name = f'{prefix}-grp'
    await _create_group_with_member(async_client, group_name, asset_name)

    slo_name = f'{prefix}-group-health'
    slo_id = await _create_slo(async_client, slo_name, sli_name)

    resp = await async_client.post(
        f'/asset-groups/{group_name}/slo-assignments',
        json={'slo_definition_id': slo_id, 'data_source_name': ds_name},
    )
    assert resp.status_code == 201

    status, body = await _evaluate(async_client, asset_name)

    assert status == 201
    assert len(body['slo_evaluation_ids']) == 1


# ---------------------------------------------------------------------------
# Test: Group -> SLO group (template) assignment
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_evaluate_group_template_assignment(
    async_client: AsyncClient, prefix: str,
) -> None:
    """SLO group assigned to asset group — template-generated SLOs discovered."""
    type_name, ds_name, sli_name = await _create_base_entities(async_client, prefix)

    asset_name = f'{prefix}-group-tmpl'
    await _create_asset(async_client, asset_name, type_name)

    group_name = f'{prefix}-tmpl-grp'
    await _create_group_with_member(async_client, group_name, asset_name)

    # Create template SLO + SLO group that generates 2 SLOs
    tpl_slo_name = f'{prefix}-tpl/$__gen_proc'
    await _create_slo(
        async_client, tpl_slo_name, sli_name,
        kind='template', variables={'proc': '$__gen_proc'},
    )

    resp = await async_client.post(
        '/slo-groups',
        json={
            'name': f'{prefix}-sg',
            'template_slo_name': tpl_slo_name,
            'template_slo_version': 1,
            'gen_variables': {'proc': ['alpha', 'beta']},
        },
    )
    assert resp.status_code == 201

    resp = await async_client.post(
        f'/asset-groups/{group_name}/slo-group-assignments',
        json={'slo_group_name': f'{prefix}-sg', 'data_source_name': ds_name},
    )
    assert resp.status_code == 201

    status, body = await _evaluate(async_client, asset_name)

    assert status == 201
    assert len(body['slo_evaluation_ids']) == 2


# ---------------------------------------------------------------------------
# Test: Direct asset -> SLO group (template) assignment
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_evaluate_direct_template_assignment(
    async_client: AsyncClient, prefix: str,
) -> None:
    """SLO group assigned directly to asset — template-generated SLOs discovered."""
    type_name, ds_name, sli_name = await _create_base_entities(async_client, prefix)

    asset_name = f'{prefix}-direct-tmpl'
    await _create_asset(async_client, asset_name, type_name)

    tpl_slo_name = f'{prefix}-dtpl/$__gen_proc'
    await _create_slo(
        async_client, tpl_slo_name, sli_name,
        kind='template', variables={'proc': '$__gen_proc'},
    )

    resp = await async_client.post(
        '/slo-groups',
        json={
            'name': f'{prefix}-dsg',
            'template_slo_name': tpl_slo_name,
            'template_slo_version': 1,
            'gen_variables': {'proc': ['gamma', 'delta']},
        },
    )
    assert resp.status_code == 201

    resp = await async_client.post(
        f'/assets/{asset_name}/slo-group-assignments',
        json={'slo_group_name': f'{prefix}-dsg', 'data_source_name': ds_name},
    )
    assert resp.status_code == 201

    status, body = await _evaluate(async_client, asset_name)

    assert status == 201
    assert len(body['slo_evaluation_ids']) == 2


# ---------------------------------------------------------------------------
# Test: Precedence — direct asset assignment wins over group assignment
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_direct_assignment_overrides_group(
    async_client: AsyncClient, prefix: str,
) -> None:
    """Same SLO name assigned both directly and via group — direct wins."""
    type_name, ds_name, sli_name = await _create_base_entities(async_client, prefix)

    # Create a second datasource to distinguish which assignment wins
    ds2_name = f'{prefix}-ds2'
    resp = await async_client.post(
        '/datasources',
        json={'name': ds2_name, 'adapter_type': 'mock', 'adapter_url': 'http://mock:8082'},
    )
    assert resp.status_code == 201

    asset_name = f'{prefix}-precedence'
    await _create_asset(async_client, asset_name, type_name)

    group_name = f'{prefix}-prec-grp'
    await _create_group_with_member(async_client, group_name, asset_name)

    slo_name = f'{prefix}-prec-slo'
    slo_id = await _create_slo(async_client, slo_name, sli_name)

    # Assign to group with ds1
    resp = await async_client.post(
        f'/asset-groups/{group_name}/slo-assignments',
        json={'slo_definition_id': slo_id, 'data_source_name': ds_name},
    )
    assert resp.status_code == 201

    # Assign directly to asset with ds2 — should win
    resp = await async_client.post(
        f'/assets/{asset_name}/slo-assignments',
        json={'slo_definition_id': slo_id, 'data_source_name': ds2_name},
    )
    assert resp.status_code == 201

    status, body = await _evaluate(async_client, asset_name)

    assert status == 201
    # Only 1 SLO evaluation (deduplicated by name, direct wins)
    assert len(body['slo_evaluation_ids']) == 1


# ---------------------------------------------------------------------------
# Test: Precedence — direct assignment wins over template-generated
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_direct_assignment_overrides_template(
    async_client: AsyncClient, prefix: str,
) -> None:
    """Direct SLO assignment overrides template-generated SLO with same name."""
    type_name, ds_name, sli_name = await _create_base_entities(async_client, prefix)

    ds2_name = f'{prefix}-ds-ot'
    resp = await async_client.post(
        '/datasources',
        json={'name': ds2_name, 'adapter_type': 'mock', 'adapter_url': 'http://mock:8082'},
    )
    assert resp.status_code == 201

    asset_name = f'{prefix}-tmpl-override'
    await _create_asset(async_client, asset_name, type_name)

    # Create template that generates SLO named "<prefix>-ot/alpha"
    tpl_slo_name = f'{prefix}-ot/$__gen_proc'
    await _create_slo(
        async_client, tpl_slo_name, sli_name,
        kind='template', variables={'proc': '$__gen_proc'},
    )

    resp = await async_client.post(
        '/slo-groups',
        json={
            'name': f'{prefix}-ot-sg',
            'template_slo_name': tpl_slo_name,
            'template_slo_version': 1,
            'gen_variables': {'proc': ['alpha']},
        },
    )
    assert resp.status_code == 201

    # Assign template group to asset
    resp = await async_client.post(
        f'/assets/{asset_name}/slo-group-assignments',
        json={'slo_group_name': f'{prefix}-ot-sg', 'data_source_name': ds_name},
    )
    assert resp.status_code == 201

    # Create a direct SLO with the SAME name the template generates
    generated_name = f'{prefix}-ot/alpha'
    direct_slo_id = await _create_slo(async_client, generated_name, sli_name)

    resp = await async_client.post(
        f'/assets/{asset_name}/slo-assignments',
        json={'slo_definition_id': direct_slo_id, 'data_source_name': ds2_name},
    )
    assert resp.status_code == 201

    status, body = await _evaluate(async_client, asset_name)

    assert status == 201
    # Only 1 evaluation — direct overrides template for same name
    assert len(body['slo_evaluation_ids']) == 1


# ---------------------------------------------------------------------------
# Test: Mixed — all binding types with different SLO names
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_mixed_binding_types_all_discovered(
    async_client: AsyncClient, prefix: str,
) -> None:
    """Asset with direct SLO + group SLO + template SLOs — all discovered."""
    type_name, ds_name, sli_name = await _create_base_entities(async_client, prefix)

    asset_name = f'{prefix}-mixed'
    await _create_asset(async_client, asset_name, type_name)

    group_name = f'{prefix}-mix-grp'
    await _create_group_with_member(async_client, group_name, asset_name)

    # 1) Direct SLO assignment
    direct_slo_name = f'{prefix}-mix-direct'
    direct_slo_id = await _create_slo(async_client, direct_slo_name, sli_name)
    resp = await async_client.post(
        f'/assets/{asset_name}/slo-assignments',
        json={'slo_definition_id': direct_slo_id, 'data_source_name': ds_name},
    )
    assert resp.status_code == 201

    # 2) Group SLO assignment (different name)
    group_slo_name = f'{prefix}-mix-group'
    group_slo_id = await _create_slo(async_client, group_slo_name, sli_name)
    resp = await async_client.post(
        f'/asset-groups/{group_name}/slo-assignments',
        json={'slo_definition_id': group_slo_id, 'data_source_name': ds_name},
    )
    assert resp.status_code == 201

    # 3) Template via group — generates 2 SLOs
    tpl_name = f'{prefix}-mix-tpl/$__gen_proc'
    await _create_slo(
        async_client, tpl_name, sli_name,
        kind='template', variables={'proc': '$__gen_proc'},
    )
    resp = await async_client.post(
        '/slo-groups',
        json={
            'name': f'{prefix}-mix-sg',
            'template_slo_name': tpl_name,
            'template_slo_version': 1,
            'gen_variables': {'proc': ['one', 'two']},
        },
    )
    assert resp.status_code == 201
    resp = await async_client.post(
        f'/asset-groups/{group_name}/slo-group-assignments',
        json={'slo_group_name': f'{prefix}-mix-sg', 'data_source_name': ds_name},
    )
    assert resp.status_code == 201

    status, body = await _evaluate(async_client, asset_name)

    assert status == 201
    # 1 direct + 1 group + 2 template = 4 SLO evaluations
    assert len(body['slo_evaluation_ids']) == 4
