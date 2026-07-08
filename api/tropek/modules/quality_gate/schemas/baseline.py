"""Pydantic schemas for baseline pinning, invalidation, and status overrides."""

from __future__ import annotations

from typing import Literal

from tropek.modules.common.schemas import SafeStr, StrictInput


class InvalidateRequest(StrictInput):
    """Request body for invalidating an evaluation."""

    invalidation_note: SafeStr


class PinBaselineRequest(StrictInput):
    """Request body for pinning an evaluation as baseline."""

    reason: SafeStr
    author: SafeStr


class OverrideStatusRequest(StrictInput):
    """Request body for overriding evaluation result."""

    new_result: Literal['pass', 'warning', 'fail']
    reason: SafeStr
    author: SafeStr
