"""Unit tests for post-commit finalization logic in queue.py."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.modules.quality_gate.evaluation_run_repository import EvaluationRunRepository


@pytest.mark.asyncio
async def test_finalize_called_after_commit():
    """Finalization must happen in a fresh session after the evaluation commit."""
    run_id = uuid.uuid4()
    mock_repo = AsyncMock(spec=EvaluationRunRepository)
    mock_repo.finalize_if_all_done.return_value = None

    # Simulate session_factory() → context manager → session
    mock_session = AsyncMock()
    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    call_count = 0

    def session_factory():
        nonlocal call_count
        call_count += 1
        return mock_session_ctx

    with patch(
        'app.queue.get_session_factory',
        return_value=session_factory,
    ), patch(
        'app.queue.run_evaluation',
        new_callable=AsyncMock,
        return_value=run_id,
    ), patch(
        'app.queue.EvaluationRunRepository',
        return_value=mock_repo,
    ), patch(
        'app.queue._has_pending_predecessor',
        new_callable=AsyncMock,
        return_value=False,
    ):
        from app.queue import run_evaluation_job

        ctx: dict = {'cache': None, 'redis': MagicMock(), 'job_id': 'test'}
        await run_evaluation_job(ctx, str(uuid.uuid4()))

    mock_repo.finalize_if_all_done.assert_awaited_once_with(run_id)
    # session_factory called twice: once for evaluation, once for finalization
    assert call_count == 2
