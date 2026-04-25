"""Integration tests for ConfigurationRepository — key-value settings CRUD."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from tropek.db.models import Configuration
from tropek.modules.configuration.repository import ConfigurationRepository


async def _seed_defaults(session: AsyncSession) -> None:
    """Insert the standard change_point.* settings for testing."""
    rows = [
        Configuration(name='change_point.enabled', value='true', value_type='bool'),
        Configuration(name='change_point.higher_is_better', value='false', value_type='bool'),
        Configuration(name='change_point.window_size', value='30', value_type='int'),
        Configuration(name='change_point.max_pvalue', value='0.001', value_type='float'),
        Configuration(name='change_point.min_magnitude', value='0.0', value_type='float'),
        Configuration(name='change_point.min_sample_size', value='10', value_type='int'),
        Configuration(name='ui.theme', value='dark', value_type='str'),
    ]
    session.add_all(rows)
    await session.flush()


@pytest.mark.integration
async def test_get_all_returns_all_entries(db_session: AsyncSession) -> None:
    """get_all() with no prefix returns every configuration row."""
    await _seed_defaults(db_session)
    repo = ConfigurationRepository(db_session)

    entries = await repo.get_all()
    assert len(entries) == 7


@pytest.mark.integration
async def test_get_all_filters_by_prefix(db_session: AsyncSession) -> None:
    """get_all(prefix='change_point.') returns only change_point settings."""
    await _seed_defaults(db_session)
    repo = ConfigurationRepository(db_session)

    entries = await repo.get_all(prefix='change_point.')
    assert len(entries) == 6
    assert all(e.name.startswith('change_point.') for e in entries)


@pytest.mark.integration
async def test_get_by_name_returns_entry(db_session: AsyncSession) -> None:
    """get_by_name returns the matching configuration entry."""
    await _seed_defaults(db_session)
    repo = ConfigurationRepository(db_session)

    entry = await repo.get_by_name('change_point.window_size')
    assert entry is not None
    assert entry.value == '30'
    assert entry.value_type == 'int'


@pytest.mark.integration
async def test_get_by_name_returns_none_for_missing(db_session: AsyncSession) -> None:
    """get_by_name returns None when the key does not exist."""
    repo = ConfigurationRepository(db_session)

    entry = await repo.get_by_name('nonexistent.key')
    assert entry is None


@pytest.mark.integration
async def test_update_value_changes_stored_value(db_session: AsyncSession) -> None:
    """update_value modifies the value and returns the updated entry."""
    await _seed_defaults(db_session)
    repo = ConfigurationRepository(db_session)

    updated = await repo.update_value('change_point.window_size', '60')
    assert updated is not None
    assert updated.value == '60'

    refreshed = await repo.get_by_name('change_point.window_size')
    assert refreshed is not None
    assert refreshed.value == '60'


@pytest.mark.integration
async def test_update_value_rejects_invalid_type(db_session: AsyncSession) -> None:
    """update_value raises ValueError when the value doesn't match the type."""
    await _seed_defaults(db_session)
    repo = ConfigurationRepository(db_session)

    with pytest.raises(ValueError, match='not a valid int'):
        await repo.update_value('change_point.window_size', 'not-a-number')


@pytest.mark.integration
async def test_update_value_returns_none_for_missing(db_session: AsyncSession) -> None:
    """update_value returns None when the key does not exist."""
    repo = ConfigurationRepository(db_session)

    result = await repo.update_value('nonexistent.key', 'value')
    assert result is None


@pytest.mark.integration
async def test_get_change_point_defaults_returns_typed_dict(
    db_session: AsyncSession,
) -> None:
    """get_change_point_defaults returns a dict with typed values."""
    await _seed_defaults(db_session)
    repo = ConfigurationRepository(db_session)

    defaults = await repo.get_change_point_defaults()

    assert defaults['enabled'] is True
    assert defaults['higher_is_better'] is False
    assert defaults['window_size'] == 30
    assert defaults['max_pvalue'] == 0.001
    assert defaults['min_magnitude'] == 0.0
    assert defaults['min_sample_size'] == 10
    assert 'theme' not in defaults


@pytest.mark.integration
async def test_update_bool_validates_values(db_session: AsyncSession) -> None:
    """Bool type accepts 'true'/'false' (case-insensitive) and rejects others."""
    await _seed_defaults(db_session)
    repo = ConfigurationRepository(db_session)

    updated = await repo.update_value('change_point.enabled', 'False')
    assert updated is not None
    assert updated.value == 'False'

    with pytest.raises(ValueError, match='not a valid bool'):
        await repo.update_value('change_point.enabled', 'yes')
