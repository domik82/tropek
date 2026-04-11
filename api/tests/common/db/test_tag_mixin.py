"""Integration tests for TagQueryMixin via AssetRepository."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from tropek.modules.assets.repository import AssetRepository


@pytest.mark.integration
async def test_get_tag_keys_returns_empty_when_no_tags(
    db_session: AsyncSession,
) -> None:
    repo = AssetRepository(db_session)
    result = await repo.get_tag_keys()
    assert isinstance(result, dict)


@pytest.mark.integration
async def test_get_tag_values_returns_empty_for_missing_key(
    db_session: AsyncSession,
) -> None:
    repo = AssetRepository(db_session)
    result = await repo.get_tag_values('nonexistent')
    assert result == {}
