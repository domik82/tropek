"""Integration tests for SLORepository.

Requires TEST_DATABASE_URL and a running TimescaleDB instance.
Run: uv run pytest api/tests/db/test_slo_repository.py -m integration -v
"""

from __future__ import annotations

import pytest
from app.modules.slo_registry.repository import SLORepository
from sqlalchemy.ext.asyncio import AsyncSession

OBJECTIVES_V1 = [{"sli": "m", "pass_criteria": ["<100"]}]
OBJECTIVES_V2 = [{"sli": "m", "pass_criteria": ["<80"]}]


@pytest.mark.integration
async def test_create_first_version(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    slo = await repo.create("my-slo", objectives=OBJECTIVES_V1, notes="Initial", author="alice")
    assert slo.version == 1
    assert slo.name == "my-slo"
    assert slo.author == "alice"


@pytest.mark.integration
async def test_create_second_version_increments(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    await repo.create("versioned-slo", objectives=OBJECTIVES_V1)
    v2 = await repo.create("versioned-slo", objectives=OBJECTIVES_V2, notes="Tightened thresholds")
    assert v2.version == 2


@pytest.mark.integration
async def test_get_latest_returns_highest_version(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    await repo.create("latest-slo", objectives=OBJECTIVES_V1)
    await repo.create("latest-slo", objectives=OBJECTIVES_V2)
    latest = await repo.get_latest("latest-slo")
    assert latest is not None
    assert latest.version == 2
    assert latest.total_score_pass_pct == 90.0
    assert latest.objectives[0].pass_criteria == ["<80"]


@pytest.mark.integration
async def test_get_version_specific(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    await repo.create("specific-slo", objectives=OBJECTIVES_V1)
    await repo.create("specific-slo", objectives=OBJECTIVES_V2)
    v1 = await repo.get_version("specific-slo", 1)
    assert v1 is not None
    assert v1.objectives[0].pass_criteria == ["<100"]


@pytest.mark.integration
async def test_list_versions_newest_first(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    await repo.create("list-slo", objectives=OBJECTIVES_V1)
    await repo.create("list-slo", objectives=OBJECTIVES_V2)
    versions = await repo.list_versions("list-slo")
    assert len(versions) == 2
    assert versions[0].version == 2
    assert versions[1].version == 1


@pytest.mark.integration
async def test_deactivate_hides_from_get_latest(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    await repo.create("delete-slo", objectives=OBJECTIVES_V1)
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
        objectives=OBJECTIVES_V1,
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
    slo = await repo.create("no-display-slo", objectives=OBJECTIVES_V1)
    assert slo.display_name is None
    fetched = await repo.get_latest("no-display-slo")
    assert fetched is not None
    assert fetched.display_name is None


@pytest.mark.integration
async def test_create_with_variables(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    slo = await repo.create(
        "slo-vars",
        objectives=[{"sli": "m1", "pass_criteria": ["<600"]}],
        tags={"team": "alpha"},
        variables={"aggregation_window": "5m"},
    )
    assert slo.tags == {"team": "alpha"}
    assert slo.variables == {"aggregation_window": "5m"}


@pytest.mark.integration
async def test_list_all_filters_by_tag(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    await repo.create("slo-a", [{"sli": "m1", "pass_criteria": ["<600"]}], tags={"env": "prod"})
    await repo.create("slo-b", [{"sli": "m2", "pass_criteria": ["<100"]}], tags={"env": "staging"})
    result = await repo.list_all(tag_key="env", tag_val="prod")
    assert len(result) == 1
    assert result[0].name == "slo-a"


@pytest.mark.integration
async def test_get_tag_keys(db_session: AsyncSession) -> None:
    repo = SLORepository(db_session)
    await repo.create(
        "slo-a",
        [{"sli": "m1", "pass_criteria": ["<600"]}],
        tags={"team": "a", "env": "prod"},
    )
    await repo.create(
        "slo-b",
        [{"sli": "m2", "pass_criteria": ["<100"]}],
        tags={"env": "staging"},
    )
    keys = await repo.get_tag_keys()
    assert keys["env"] == 2
    assert keys["team"] == 1
