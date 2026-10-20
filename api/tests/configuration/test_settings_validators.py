"""Timeout-chain validation of the worker settings."""

from __future__ import annotations

from typing import Any

import pytest
from tropek.config import QueueSettings, ReliabilitySettings, validate_timeout_chain


def test_shipped_defaults_are_consistent() -> None:
    validate_timeout_chain(
        ReliabilitySettings(adapter_timeout_seconds=330, stuck_job_threshold_seconds=600),
        QueueSettings(job_timeout_seconds=400),
    )


def test_smallest_consistent_chain_is_accepted() -> None:
    """The adapter waits budget + 5 s (35 s at the floor); the job keeps more than 60 s beyond one attempt."""
    validate_timeout_chain(
        ReliabilitySettings(adapter_timeout_seconds=36, stuck_job_threshold_seconds=98),
        QueueSettings(job_timeout_seconds=97),
    )


def test_negative_max_retries_is_refused() -> None:
    with pytest.raises(ValueError, match='max_retries must be >= 0'):
        QueueSettings(max_retries=-1)


def test_adapter_budget_is_timeout_minus_margin_floored() -> None:
    assert ReliabilitySettings(adapter_timeout_seconds=330).adapter_budget_seconds == 300
    assert ReliabilitySettings(adapter_timeout_seconds=40).adapter_budget_seconds == 30


@pytest.mark.parametrize(
    ('reliability', 'queue', 'message'),
    [
        ({'adapter_timeout_seconds': 30}, {}, 'adapter_timeout_seconds must exceed 35'),
        ({'adapter_timeout_seconds': 35}, {}, 'adapter_timeout_seconds must exceed 35'),
        (
            {'adapter_timeout_seconds': 330},
            {'job_timeout_seconds': 300},
            'job_timeout_seconds must exceed adapter_timeout_seconds by more than 60',
        ),
        (
            # Exactly +60 leaves the client's deadline equal to one attempt: every attempt would be refused.
            {'adapter_timeout_seconds': 330},
            {'job_timeout_seconds': 390},
            'job_timeout_seconds must exceed adapter_timeout_seconds by more than 60',
        ),
        (
            {'adapter_timeout_seconds': 330, 'stuck_job_threshold_seconds': 400},
            {'job_timeout_seconds': 400},
            'stuck_job_threshold_seconds must exceed job_timeout_seconds',
        ),
        (
            {'adapter_timeout_seconds': 700},
            {'job_timeout_seconds': 800},
            'adapter budget 670 exceeds the adapter maximum 600',
        ),
    ],
)
def test_inconsistent_chain_is_refused(reliability: dict[str, Any], queue: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        validate_timeout_chain(ReliabilitySettings(**reliability), QueueSettings(**queue))
