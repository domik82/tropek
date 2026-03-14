"""Integration tests for SLIRepository."""

from __future__ import annotations

import pytest
from app.modules.sli_registry.repository import SLIRepository
from sqlalchemy.ext.asyncio import AsyncSession

_INDICATORS = {
    "response_time_p95": 'histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{instance="$vm_ip"}[5m]))',
    "cpu_usage_avg": 'avg_over_time(process_cpu_seconds_total{instance="$vm_ip"}[5m])',
}


@pytest.mark.integration
async def test_create_first_version(db_session: AsyncSession) -> None:
    repo = SLIRepository(db_session)
    sli = await repo.create(name="linux-sli", indicators=_INDICATORS)
    assert sli.version == 1
    assert sli.name == "linux-sli"
    assert sli.indicators == _INDICATORS
    assert sli.active is True


@pytest.mark.integration
async def test_create_increments_version(db_session: AsyncSession) -> None:
    repo = SLIRepository(db_session)
    await repo.create(name="versioned-sli", indicators=_INDICATORS)
    v2 = await repo.create(name="versioned-sli", indicators={"cpu": "some_query"})
    assert v2.version == 2


@pytest.mark.integration
async def test_get_latest_returns_highest_version(db_session: AsyncSession) -> None:
    repo = SLIRepository(db_session)
    await repo.create(name="latest-sli", indicators={"a": "q1"})
    await repo.create(name="latest-sli", indicators={"a": "q2"})
    latest = await repo.get_latest("latest-sli")
    assert latest is not None
    assert latest.version == 2
    assert latest.indicators == {"a": "q2"}


@pytest.mark.integration
async def test_get_version_returns_specific(db_session: AsyncSession) -> None:
    repo = SLIRepository(db_session)
    await repo.create(name="pinned-sli", indicators={"a": "q1"})
    await repo.create(name="pinned-sli", indicators={"a": "q2"})
    v1 = await repo.get_version("pinned-sli", 1)
    assert v1 is not None
    assert v1.indicators == {"a": "q1"}


@pytest.mark.integration
async def test_get_latest_returns_none_for_unknown(db_session: AsyncSession) -> None:
    repo = SLIRepository(db_session)
    result = await repo.get_latest("does-not-exist")
    assert result is None


@pytest.mark.integration
async def test_deactivate_hides_from_get_latest(db_session: AsyncSession) -> None:
    repo = SLIRepository(db_session)
    await repo.create(name="gone-sli", indicators={"a": "q1"})
    await repo.deactivate("gone-sli")
    result = await repo.get_latest("gone-sli")
    assert result is None
