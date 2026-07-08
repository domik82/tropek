"""Pydantic schemas for bulk (batch) evaluation-action endpoints.

Each request carries a list of evaluation ids plus the same fields as its
singular counterpart in ``baseline.py``. The shared response reports the
per-id outcomes, the number of rows updated, and any ids that were not found
or skipped (unknown id, or a precondition such as "not completed" not met).
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel

from tropek.modules.common.schemas import SafeStr, StrictInput


class InvalidateManyRequest(StrictInput):
    """Request body for PATCH /evaluations/invalidate."""

    evaluation_ids: list[uuid.UUID]
    note: SafeStr


class RestoreManyRequest(StrictInput):
    """Request body for PATCH /evaluations/restore."""

    evaluation_ids: list[uuid.UUID]


class OverrideStatusManyRequest(StrictInput):
    """Request body for PATCH /evaluations/override-status."""

    evaluation_ids: list[uuid.UUID]
    new_result: Literal['pass', 'warning', 'fail']
    reason: SafeStr
    author: SafeStr


class RestoreOverrideManyRequest(StrictInput):
    """Request body for PATCH /evaluations/restore-override."""

    evaluation_ids: list[uuid.UUID]


class PinBaselineManyRequest(StrictInput):
    """Request body for PATCH /evaluations/pin-baseline."""

    evaluation_ids: list[uuid.UUID]
    reason: SafeStr
    author: SafeStr


class UnpinBaselineManyRequest(StrictInput):
    """Request body for PATCH /evaluations/unpin-baseline."""

    evaluation_ids: list[uuid.UUID]


class BulkActionResult(BaseModel):
    """Outcome for a single evaluation id in a bulk action."""

    evaluation_id: uuid.UUID
    status: Literal['success']


class BulkActionResponse(BaseModel):
    """Response for every bulk evaluation-action endpoint.

    ``not_found`` collects ids that were not applied — either unknown, or
    skipped because a precondition (e.g. status must be completed) was not met.
    """

    results: list[BulkActionResult]
    updated: int
    not_found: list[uuid.UUID]
