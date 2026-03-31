"""Unit tests for worker rollup logic."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.quality_gate.worker import _try_rollup_parent


@pytest.mark.asyncio
async def test_try_rollup_parent_calls_repository():
    mock_session = MagicMock()
    mock_repo = AsyncMock()
    mock_repo.rollup_if_all_done.return_value = None

    with patch(
        'app.modules.quality_gate.worker.EvaluationRunRepository',
        return_value=mock_repo,
    ):
        run_id = uuid.uuid4()
        await _try_rollup_parent(mock_session, run_id, MagicMock())
        mock_repo.rollup_if_all_done.assert_awaited_once_with(run_id)
