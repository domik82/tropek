"""Unit tests for evaluation trigger resolution logic."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from app.modules.assignments.repository import ResolvedAssignment
from app.modules.quality_gate.shared.exceptions import AssetNotFoundError, SLONotConfiguredError
from app.modules.quality_gate.trigger import (
    resolve_all_slos_for_asset,
    resolve_single_trigger,
)


def _make_asset(name: str = 'vm-01') -> object:
    return type(
        'Asset',
        (),
        {
            'id': uuid.uuid4(),
            'name': name,
            'display_name': 'Production VM 01',
            'tags': {'os': 'linux'},
            'variables': {},
        },
    )()


def _make_slo(
    name: str = 'perf-slo',
    *,
    slo_id: uuid.UUID | None = None,
    sli_name: str | None = 'system-sli',
    sli_version: int | None = None,
    sli_definition_id: uuid.UUID | None = None,
) -> object:
    return type(
        'SLO',
        (),
        {
            'id': slo_id or uuid.uuid4(),
            'name': name,
            'version': 1,
            'sli_name': sli_name,
            'sli_version': sli_version,
            'sli_definition_id': sli_definition_id,
        },
    )()


def _make_sli(name: str = 'system-sli') -> object:
    return type(
        'SLI',
        (),
        {'id': uuid.uuid4(), 'name': name, 'version': 1, 'indicators': {'cpu': 'query'}},
    )()


def _make_ds(name: str = 'prom-1') -> object:
    return type(
        'DS',
        (),
        {'name': name, 'adapter_url': 'http://prom:8081', 'adapter_type': 'prometheus'},
    )()


@pytest.fixture
def mock_repos() -> dict:
    asset_repo = AsyncMock()
    sli_repo = AsyncMock()
    slo_repo = AsyncMock()
    ds_repo = AsyncMock()
    assignment_repo = AsyncMock()

    asset = _make_asset()
    slo_def = _make_slo(slo_id=uuid.uuid4())
    sli_def = _make_sli()
    ds = _make_ds()
    ds_id = uuid.uuid4()

    asset_repo.get_by_name.return_value = asset

    assignment_repo.find_for_asset.return_value = ResolvedAssignment(
        slo_name='perf-slo',
        slo_definition_id=slo_def.id,
        data_source_id=ds_id,
        comparison_rules=None,
        source='direct_asset',
    )

    # slo_def.sli_definition_id must be set so trigger.py can look up SLI by FK
    slo_def.sli_definition_id = sli_def.id

    slo_repo.get_by_id.return_value = slo_def
    sli_repo.get_by_id.return_value = sli_def
    ds_repo.get_by_id.return_value = ds

    return {
        'asset_repo': asset_repo,
        'sli_repo': sli_repo,
        'slo_repo': slo_repo,
        'ds_repo': ds_repo,
        'assignment_repo': assignment_repo,
        'group_ids': [],
    }


async def test_resolve_single_trigger(mock_repos: dict) -> None:
    ctx = await resolve_single_trigger(asset_name='vm-01', slo_name='perf-slo', **mock_repos)
    assert ctx.asset_name == 'vm-01'
    assert ctx.slo_name == 'perf-slo'
    assert ctx.sli_name == 'system-sli'
    assert ctx.data_source_name == 'prom-1'
    assert ctx.adapter_url == 'http://prom:8081'
    assert ctx.indicators == {'cpu': 'query'}


async def test_resolve_single_trigger_asset_not_found(mock_repos: dict) -> None:
    mock_repos['asset_repo'].get_by_name.return_value = None
    with pytest.raises(AssetNotFoundError, match='asset'):
        await resolve_single_trigger(asset_name='nonexistent', slo_name='perf-slo', **mock_repos)


async def test_resolve_no_assignment_raises(mock_repos: dict) -> None:
    """When no assignment exists, raise SLONotConfiguredError."""
    mock_repos['assignment_repo'].find_for_asset.return_value = None
    with pytest.raises(SLONotConfiguredError, match='no assignment'):
        await resolve_single_trigger(asset_name='vm-01', slo_name='unknown-slo', **mock_repos)


async def test_trigger_context_includes_display_name(mock_repos: dict) -> None:
    ctx = await resolve_single_trigger(asset_name='vm-01', slo_name='perf-slo', **mock_repos)
    assert ctx.asset_display_name == 'Production VM 01'


async def test_trigger_context_includes_slo_definition_id(mock_repos: dict) -> None:
    """TriggerContext carries the slo_definition_id FK."""
    ctx = await resolve_single_trigger(asset_name='vm-01', slo_name='perf-slo', **mock_repos)
    assert ctx.slo_definition_id is not None


async def test_resolve_all_slos_for_asset() -> None:
    """resolve_all_slos_for_asset returns sorted SLO names from assignment_repo."""
    asset_id = uuid.uuid4()
    ds_id = uuid.uuid4()

    assignment_repo = AsyncMock()
    assignment_repo.resolve_for_asset.return_value = [
        ResolvedAssignment(
            slo_name='direct-slo',
            slo_definition_id=uuid.uuid4(),
            data_source_id=ds_id,
            comparison_rules=None,
            source='direct_asset',
        ),
        ResolvedAssignment(
            slo_name='gen-slo-a',
            slo_definition_id=uuid.uuid4(),
            data_source_id=ds_id,
            comparison_rules=None,
            source='template_asset',
        ),
        ResolvedAssignment(
            slo_name='gen-slo-b',
            slo_definition_id=uuid.uuid4(),
            data_source_id=ds_id,
            comparison_rules=None,
            source='template_asset',
        ),
    ]

    result = await resolve_all_slos_for_asset(
        asset_id=asset_id,
        group_ids=[],
        assignment_repo=assignment_repo,
    )

    assert result == ['direct-slo', 'gen-slo-a', 'gen-slo-b']


async def test_resolve_all_slos_dedup_by_assignment_repo() -> None:
    """resolve_all_slos_for_asset trusts the assignment_repo's dedup — each name appears once."""
    asset_id = uuid.uuid4()
    ds_id = uuid.uuid4()

    assignment_repo = AsyncMock()
    # assignment_repo already performs dedup (DISTINCT ON slo_name with precedence)
    assignment_repo.resolve_for_asset.return_value = [
        ResolvedAssignment(
            slo_name='shared-slo',
            slo_definition_id=uuid.uuid4(),
            data_source_id=ds_id,
            comparison_rules=None,
            source='direct_asset',
        ),
    ]

    result = await resolve_all_slos_for_asset(
        asset_id=asset_id,
        group_ids=[],
        assignment_repo=assignment_repo,
    )

    assert result == ['shared-slo']
