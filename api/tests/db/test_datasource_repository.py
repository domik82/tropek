"""Integration tests for DataSourceRepository."""

from __future__ import annotations

import pytest
from app.modules.datasource.repository import DataSourceRepository
from sqlalchemy.ext.asyncio import AsyncSession


def _ds_kwargs(**overrides: object) -> dict:
    return {
        "name": "prometheus-dc-a",
        "adapter_type": "prometheus",
        "adapter_url": "http://adapter-prometheus-dc-a:8081",
        **overrides,
    }


@pytest.mark.integration
async def test_create_and_get(db_session: AsyncSession) -> None:
    repo = DataSourceRepository(db_session)
    ds = await repo.create(**_ds_kwargs())
    fetched = await repo.get_by_name("prometheus-dc-a")
    assert fetched is not None
    assert fetched.id == ds.id
    assert fetched.adapter_type == "prometheus"


@pytest.mark.integration
async def test_get_by_name_missing_returns_none(db_session: AsyncSession) -> None:
    repo = DataSourceRepository(db_session)
    result = await repo.get_by_name("does-not-exist")
    assert result is None


@pytest.mark.integration
async def test_list_all(db_session: AsyncSession) -> None:
    repo = DataSourceRepository(db_session)
    await repo.create(**_ds_kwargs(name="ds-1"))
    await repo.create(**_ds_kwargs(name="ds-2", adapter_url="http://other:8082"))
    all_ds = await repo.list_all()
    names = {ds.name for ds in all_ds}
    assert "ds-1" in names
    assert "ds-2" in names


@pytest.mark.integration
async def test_delete_removes_record(db_session: AsyncSession) -> None:
    repo = DataSourceRepository(db_session)
    ds = await repo.create(**_ds_kwargs(name="to-delete"))
    await repo.delete(ds.id)
    result = await repo.get_by_name("to-delete")
    assert result is None


@pytest.mark.integration
async def test_update_adapter_url(db_session: AsyncSession) -> None:
    repo = DataSourceRepository(db_session)
    await repo.create(**_ds_kwargs(name="ds-update"))
    updated = await repo.update("ds-update", adapter_url="http://new-addr:9090")
    assert updated.adapter_url == "http://new-addr:9090"


@pytest.mark.integration
async def test_list_all_filter_by_adapter_type(db_session: AsyncSession) -> None:
    repo = DataSourceRepository(db_session)
    await repo.create(**_ds_kwargs(name="prom-1", adapter_type="prometheus"))
    await repo.create(
        **_ds_kwargs(name="pg-1", adapter_type="postgres", adapter_url="http://pg:5432")
    )
    prom_only = await repo.list_all(adapter_type="prometheus")
    names = {ds.name for ds in prom_only}
    assert "prom-1" in names
    assert "pg-1" not in names
