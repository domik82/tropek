"""Integration tests for comparison rules on AssetSLOLink."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from app.db.models import AssetType
from app.modules.assets.comparison_rules import validate_comparison_rules
from app.modules.assets.repository import AssetRepository, AssetSLOLinkRepository
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture(autouse=True)
async def seed_asset_types(db_session: AsyncSession) -> None:
    """Seed asset types required by FK constraints."""
    for name in ('vm',):
        result = await db_session.execute(select(AssetType).where(AssetType.name == name))
        if result.scalar_one_or_none() is None:
            db_session.add(AssetType(name=name, is_default=False))
    await db_session.flush()


async def _create_asset_with_link(
    session: AsyncSession,
) -> tuple[uuid.UUID, str]:
    """Helper: create an asset with an SLO link. Returns (asset_id, asset_name)."""
    asset_repo = AssetRepository(session)
    asset = await asset_repo.create(f'cr-test-{uuid.uuid4().hex[:8]}', type_name='vm')
    link_repo = AssetSLOLinkRepository(session)
    await link_repo.create(
        asset_id=asset.id,
        link_name='perf-check',
        slo_name='http-slo',
        sli_name='http-sli',
        data_source_name='prometheus-a',
    )
    return asset.id, asset.name


@pytest.mark.integration
async def test_get_by_link_name(db_session: AsyncSession) -> None:
    """get_by_link_name returns the link matching asset_id + link_name."""
    asset_id, _ = await _create_asset_with_link(db_session)
    repo = AssetSLOLinkRepository(db_session)

    link = await repo.get_by_link_name(asset_id, 'perf-check')
    assert link is not None
    assert link.link_name == 'perf-check'
    assert link.slo_name == 'http-slo'


@pytest.mark.integration
async def test_get_by_link_name_returns_none(db_session: AsyncSession) -> None:
    """Returns None when no link with that name exists."""
    asset_id, _ = await _create_asset_with_link(db_session)
    repo = AssetSLOLinkRepository(db_session)

    link = await repo.get_by_link_name(asset_id, 'nonexistent')
    assert link is None


@pytest.mark.integration
async def test_get_by_asset_and_slo(db_session: AsyncSession) -> None:
    """get_by_asset_and_slo returns the link matching asset_id + slo_name."""
    asset_id, _ = await _create_asset_with_link(db_session)
    repo = AssetSLOLinkRepository(db_session)

    link = await repo.get_by_asset_and_slo(asset_id, 'http-slo')
    assert link is not None
    assert link.slo_name == 'http-slo'
    assert link.asset_id == asset_id


@pytest.mark.integration
async def test_get_by_asset_and_slo_returns_none(db_session: AsyncSession) -> None:
    """Returns None when no link matches that slo_name."""
    asset_id, _ = await _create_asset_with_link(db_session)
    repo = AssetSLOLinkRepository(db_session)

    link = await repo.get_by_asset_and_slo(asset_id, 'nonexistent-slo')
    assert link is None


@pytest.mark.integration
async def test_update_comparison_rules(db_session: AsyncSession) -> None:
    """Comparison rules are persisted and retrievable."""
    asset_id, _ = await _create_asset_with_link(db_session)
    repo = AssetSLOLinkRepository(db_session)

    link = await repo.get_by_link_name(asset_id, 'perf-check')
    assert link is not None
    assert link.comparison_rules == []

    rules = [
        {'match': {'branch': 'main'}, 'compare_to': {'branch': 'main'}},
        {'match': {'branch': '!main'}, 'compare_to': {'branch': 'main'}},
        {'match': {}, 'compare_to': {}},
    ]
    validated = validate_comparison_rules(rules)
    await repo.update_comparison_rules(
        link.id,
        [r.model_dump() for r in validated],
    )

    updated = await repo.get_by_link_name(asset_id, 'perf-check')
    assert updated is not None
    assert len(updated.comparison_rules) == 3
    assert updated.comparison_rules[0]['match'] == {'branch': 'main'}
    assert updated.comparison_rules[2]['match'] == {}


@pytest.mark.integration
async def test_update_comparison_rules_clear(db_session: AsyncSession) -> None:
    """Setting rules to empty list clears them."""
    asset_id, _ = await _create_asset_with_link(db_session)
    repo = AssetSLOLinkRepository(db_session)

    link = await repo.get_by_link_name(asset_id, 'perf-check')
    assert link is not None

    # Set rules
    await repo.update_comparison_rules(
        link.id,
        [{'match': {'branch': 'main'}, 'compare_to': {'branch': 'main'}}],
    )
    updated = await repo.get_by_link_name(asset_id, 'perf-check')
    assert updated is not None
    assert len(updated.comparison_rules) == 1

    # Clear rules
    await repo.update_comparison_rules(link.id, [])
    cleared = await repo.get_by_link_name(asset_id, 'perf-check')
    assert cleared is not None
    assert cleared.comparison_rules == []


@pytest.mark.integration
async def test_comparison_rules_default_empty(db_session: AsyncSession) -> None:
    """New links have comparison_rules = [] by default."""
    asset_id, _ = await _create_asset_with_link(db_session)
    repo = AssetSLOLinkRepository(db_session)
    link = await repo.get_by_link_name(asset_id, 'perf-check')
    assert link is not None
    assert link.comparison_rules == []
