"""Pydantic schemas for baseline pinning, invalidation, and status overrides."""

from __future__ import annotations

from tropek.modules.common.schemas import StrictInput


class InvalidateRequest(StrictInput):
    """Request body for invalidating an evaluation."""

    invalidation_note: str


class PinBaselineRequest(StrictInput):
    """Request body for pinning an evaluation as baseline."""

    reason: str
    author: str


class OverrideStatusRequest(StrictInput):
    """Request body for overriding evaluation result."""

    new_result: str
    reason: str
    author: str
