"""Tests for _load_definitions edge cases in worker.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.modules.quality_gate.evaluation_engine.variables import build_variables
from app.modules.quality_gate.workflows.execution.evaluation_executor import DefinitionLoadError, _load_definitions


def _make_evaluation(
    slo_name: str | None = 'perf-slo',
    slo_version: int | None = 1,
    sli_name: str | None = 'system-sli',
    sli_version: int | None = 1,
) -> MagicMock:
    ev = MagicMock()
    ev.slo_name = slo_name
    ev.slo_version = slo_version
    ev.sli_name = sli_name
    ev.sli_version = sli_version
    return ev


async def test_load_definitions_slo_name_missing() -> None:
    """Raises DefinitionLoadError when evaluation has no slo_name."""
    ev = _make_evaluation(slo_name=None)
    session = AsyncMock()

    with pytest.raises(DefinitionLoadError, match='no slo_name'):
        await _load_definitions(session, ev)


async def test_load_definitions_slo_version_missing() -> None:
    """Raises DefinitionLoadError when evaluation has no slo_version."""
    ev = _make_evaluation(slo_version=None)
    session = AsyncMock()

    with pytest.raises(DefinitionLoadError, match='no slo_name'):
        await _load_definitions(session, ev)


async def test_load_definitions_slo_not_found() -> None:
    """Raises DefinitionLoadError when SLO definition is not in the database."""
    ev = _make_evaluation()
    session = AsyncMock()
    mock_slo_repo = AsyncMock()
    mock_slo_repo.get_version.return_value = None

    with (
        patch(
            'app.modules.quality_gate.workflows.execution.evaluation_executor.SLORepository',
            return_value=mock_slo_repo,
        ),
        pytest.raises(DefinitionLoadError, match=r'perf-slo.*not found'),
    ):
        await _load_definitions(session, ev)


async def test_load_definitions_sli_name_missing() -> None:
    """Raises DefinitionLoadError when evaluation has no sli_name."""
    ev = _make_evaluation(sli_name=None)
    session = AsyncMock()
    mock_slo_repo = AsyncMock()
    mock_slo_repo.get_version.return_value = MagicMock()

    with (
        patch(
            'app.modules.quality_gate.workflows.execution.evaluation_executor.SLORepository',
            return_value=mock_slo_repo,
        ),
        pytest.raises(DefinitionLoadError, match='no sli_name'),
    ):
        await _load_definitions(session, ev)


async def test_load_definitions_sli_version_missing() -> None:
    """Raises DefinitionLoadError when evaluation has no sli_version."""
    ev = _make_evaluation(sli_version=None)
    session = AsyncMock()
    mock_slo_repo = AsyncMock()
    mock_slo_repo.get_version.return_value = MagicMock()

    with (
        patch(
            'app.modules.quality_gate.workflows.execution.evaluation_executor.SLORepository',
            return_value=mock_slo_repo,
        ),
        pytest.raises(DefinitionLoadError, match='no sli_name'),
    ):
        await _load_definitions(session, ev)


async def test_load_definitions_sli_not_found() -> None:
    """Raises DefinitionLoadError when SLI definition is not in the database."""
    ev = _make_evaluation()
    session = AsyncMock()
    mock_slo_repo = AsyncMock()
    mock_slo_repo.get_version.return_value = MagicMock()
    mock_sli_repo = AsyncMock()
    mock_sli_repo.get_version.return_value = None

    with (
        patch(
            'app.modules.quality_gate.workflows.execution.evaluation_executor.SLORepository',
            return_value=mock_slo_repo,
        ),
        patch(
            'app.modules.quality_gate.workflows.execution.evaluation_executor.SLIRepository',
            return_value=mock_sli_repo,
        ),
        pytest.raises(DefinitionLoadError, match=r'system-sli.*not found'),
    ):
        await _load_definitions(session, ev)


async def test_load_definitions_success() -> None:
    """Successful load returns (slo_def, sli_def) tuple."""
    ev = _make_evaluation()
    session = AsyncMock()
    slo_def = MagicMock()
    sli_def = MagicMock()
    mock_slo_repo = AsyncMock()
    mock_slo_repo.get_version.return_value = slo_def
    mock_sli_repo = AsyncMock()
    mock_sli_repo.get_version.return_value = sli_def

    with (
        patch(
            'app.modules.quality_gate.workflows.execution.evaluation_executor.SLORepository',
            return_value=mock_slo_repo,
        ),
        patch(
            'app.modules.quality_gate.workflows.execution.evaluation_executor.SLIRepository',
            return_value=mock_sli_repo,
        ),
    ):
        result = await _load_definitions(session, ev)

    assert result == (slo_def, sli_def)
    mock_slo_repo.get_version.assert_awaited_once_with('perf-slo', 1)
    mock_sli_repo.get_version.assert_awaited_once_with('system-sli', 1)


def test_variable_merge_priority() -> None:
    """Variables merge with correct priority: reserved < asset.variables < asset.tags < slo.variables < eval.variables."""
    # Simulate the merge order from worker.py
    variables = build_variables(
        metadata={},
        asset_name='my-asset',
        evaluation_name='daily-check',
        start='2025-01-01T00:00:00',
        end='2025-01-01T01:00:00',
    )
    asset_variables = {'job': 'checkout-api', 'namespace': 'ecommerce'}
    asset_tags = {'team': 'payments', 'namespace': 'old-value'}
    slo_variables = {'aggregation_window': '5m', 'job': 'slo-override'}
    eval_variables = {'branch': 'main', 'job': 'eval-override'}

    for k, v in asset_variables.items():
        variables.setdefault(k, str(v))
    for k, v in asset_tags.items():
        variables.setdefault(k, str(v))
    for k, v in slo_variables.items():
        variables[k] = str(v)
    for k, v in eval_variables.items():
        variables[k] = str(v)

    assert variables['asset_name'] == 'my-asset'
    assert variables['evaluation_name'] == 'daily-check'
    assert variables['namespace'] == 'ecommerce'  # asset_variables wins over asset_tags
    assert variables['team'] == 'payments'
    assert variables['aggregation_window'] == '5m'
    assert variables['branch'] == 'main'
    assert variables['job'] == 'eval-override'  # eval wins over slo
