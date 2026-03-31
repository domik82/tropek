"""Integration tests for comparison rules on SLOBinding."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from app.db.models import AssetType
from app.modules.assets.comparison_rules import validate_comparison_rules
from app.modules.assets.repository import AssetRepository, SLOBindingRepository
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture(autouse=True)
async def seed_asset_types(db_session: AsyncSession) -> None:
    for name in ('vm',):
        result = await db_session.execute(select(AssetType).where(AssetType.name == name))
        if result.scalar_one_or_none() is None:
            db_session.add(AssetType(name=name, is_default=False))
    await db_session.flush()


async def _create_asset_with_binding(session: AsyncSession) -> tuple[uuid.UUID, str]:
    """Helper: create an asset with a direct SLO binding. Returns (asset_id, asset_name)."""
    asset_repo = AssetRepository(session)
    asset = await asset_repo.create(f'cr-test-{uuid.uuid4().hex[:8]}', type_name='vm')
    binding_repo = SLOBindingRepository(session)
    await binding_repo.create(
        target_type='asset',
        target_id=asset.id,
        slo_name='http-slo',
        data_source_name='prometheus-a',
    )
    return asset.id, asset.name


@pytest.mark.integration
async def test_comparison_rules_default_none(db_session: AsyncSession) -> None:
    """New bindings have comparison_rules = None by default."""
    asset_id, _ = await _create_asset_with_binding(db_session)
    repo = SLOBindingRepository(db_session)
    binding = await repo.find_for_asset(asset_id, 'http-slo')
    assert binding is not None
    assert binding.comparison_rules is None


@pytest.mark.integration
async def test_update_comparison_rules(db_session: AsyncSession) -> None:
    """Comparison rules are persisted and retrievable."""
    asset_id, _ = await _create_asset_with_binding(db_session)
    repo = SLOBindingRepository(db_session)

    rules = [
        {'match': {'branch': 'main'}, 'compare_to': {'branch': 'main'}},
        {'match': {'branch': '!main'}, 'compare_to': {'branch': 'main'}},
        {'match': {}, 'compare_to': {}},
    ]
    validated = validate_comparison_rules(rules)
    await repo.update_comparison_rules(
        'asset', asset_id, 'http-slo',
        [r.model_dump() for r in validated],
    )

    binding = await repo.find_for_asset(asset_id, 'http-slo')
    assert binding is not None
    assert len(binding.comparison_rules) == 3
    assert binding.comparison_rules[0]['match'] == {'branch': 'main'}


@pytest.mark.integration
async def test_update_comparison_rules_clear(db_session: AsyncSession) -> None:
    """Setting rules to empty list clears them."""
    asset_id, _ = await _create_asset_with_binding(db_session)
    repo = SLOBindingRepository(db_session)

    await repo.update_comparison_rules('asset', asset_id, 'http-slo', [{'match': {}, 'compare_to': {}}])
    await repo.update_comparison_rules('asset', asset_id, 'http-slo', [])
    binding = await repo.find_for_asset(asset_id, 'http-slo')
    assert binding is not None
    assert binding.comparison_rules == []
