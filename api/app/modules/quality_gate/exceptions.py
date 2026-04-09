"""Domain exception types for the quality gate module.

These are transitional — callers should migrate to common.exceptions directly.
"""

from __future__ import annotations

from app.modules.common.exceptions import (
    ConflictError,
    DomainValidationError,
    NotFoundError,
)


class EvaluationError(DomainValidationError):
    """Precondition not met for evaluation (e.g. no SLO assignments)."""

    def __init__(self, msg: str = '') -> None:
        super().__init__(msg or 'evaluation precondition not met')


class AssetNotFoundError(NotFoundError):
    """Asset does not exist."""

    def __init__(self, msg: str = '') -> None:
        super().__init__('asset', msg)


class SLONotConfiguredError(DomainValidationError):
    """No SLO linked to asset."""

    def __init__(self, msg: str = '') -> None:
        super().__init__(msg or 'no slo configured')


class DataSourceNotFoundError(NotFoundError):
    """Data source adapter not found."""

    def __init__(self, msg: str = '') -> None:
        super().__init__('data source', msg)


class DuplicateEvaluationError(ConflictError):
    """Evaluation with same parameters already running/completed."""

    def __init__(self, msg: str = '') -> None:
        super().__init__('evaluation', msg, 'duplicate')


class EvaluationNotFoundError(NotFoundError):
    """Evaluation ID does not exist."""

    def __init__(self, msg: str = '') -> None:
        super().__init__('evaluation', msg)
