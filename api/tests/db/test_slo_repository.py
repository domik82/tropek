"""Integration tests for SLORepository.

Requires TEST_DATABASE_URL and a running TimescaleDB instance.
Run: uv run pytest api/tests/db/test_slo_repository.py -m integration -v
"""

from __future__ import annotations

import pytest
from app.modules.slo_registry.repository import SLORepository
from sqlalchemy.ext.asyncio import AsyncSession

YAML_V1 = "spec_version: '1.0'\ntotal_score:\n  pass: '90%'\n  warning: '75%'\n"
YAML_V2 = "spec_version: '1.0'\ntotal_score:\n  pass: '95%'\n  warning: '80%'\n"


@pytest.mark.integration
async def test_create_first_version(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    slo = await repo.create("my-slo", YAML_V1, notes="Initial", author="alice")
    assert slo.version == 1
    assert slo.name == "my-slo"
    assert slo.author == "alice"


@pytest.mark.integration
async def test_create_second_version_increments(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    await repo.create("versioned-slo", YAML_V1)
    v2 = await repo.create("versioned-slo", YAML_V2, notes="Tightened thresholds")
    assert v2.version == 2


@pytest.mark.integration
async def test_get_latest_returns_highest_version(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    await repo.create("latest-slo", YAML_V1)
    await repo.create("latest-slo", YAML_V2)
    latest = await repo.get_latest("latest-slo")
    assert latest is not None
    assert latest.version == 2
    assert latest.slo_yaml == YAML_V2


@pytest.mark.integration
async def test_get_version_specific(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    await repo.create("specific-slo", YAML_V1)
    await repo.create("specific-slo", YAML_V2)
    v1 = await repo.get_version("specific-slo", 1)
    assert v1 is not None
    assert v1.slo_yaml == YAML_V1


@pytest.mark.integration
async def test_list_versions_newest_first(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    await repo.create("list-slo", YAML_V1)
    await repo.create("list-slo", YAML_V2)
    versions = await repo.list_versions("list-slo")
    assert len(versions) == 2
    assert versions[0].version == 2
    assert versions[1].version == 1


@pytest.mark.integration
async def test_deactivate_hides_from_get_latest(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    await repo.create("delete-slo", YAML_V1)
    deleted = await repo.deactivate("delete-slo")
    assert deleted == 1
    result = await repo.get_latest("delete-slo")
    assert result is None


@pytest.mark.integration
async def test_get_latest_nonexistent_returns_none(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    result = await repo.get_latest("does-not-exist")
    assert result is None


@pytest.mark.integration
async def test_create_with_display_name_stores_and_retrieves(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    slo = await repo.create(
        "display-name-slo",
        YAML_V1,
        display_name="My Test SLO",
        author="alice",
    )
    assert slo.display_name == "My Test SLO"
    fetched = await repo.get_latest("display-name-slo")
    assert fetched is not None
    assert fetched.display_name == "My Test SLO"


@pytest.mark.integration
async def test_create_without_display_name_defaults_to_none(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    slo = await repo.create("no-display-slo", YAML_V1)
    assert slo.display_name is None
    fetched = await repo.get_latest("no-display-slo")
    assert fetched is not None
    assert fetched.display_name is None
