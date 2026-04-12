"""Domain exception types specific to the quality gate module.

Generic exceptions (NotFoundError, ConflictError, DomainValidationError) live in
common.exceptions. Only quality-gate-specific semantics belong here.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from tropek.modules.common.exceptions import DomainValidationError


class EvaluationError(DomainValidationError):
    """Precondition not met for evaluation (e.g. no SLO assignments)."""

    def __init__(self, msg: str = '') -> None:
        super().__init__(msg or 'evaluation precondition not met')


class SLONotConfiguredError(DomainValidationError):
    """No SLO linked to asset."""

    def __init__(self, msg: str = '') -> None:
        super().__init__(msg or 'no slo configured')


class BaselinePinConflictError(Exception):
    """Raised when re-evaluation from_date is before the active baseline pin."""

    def __init__(self, pin_date: datetime, pin_evaluation_id: uuid.UUID) -> None:
        self.pin_date = pin_date
        self.pin_evaluation_id = pin_evaluation_id
        super().__init__('re-evaluation start date is before the active baseline pin')
