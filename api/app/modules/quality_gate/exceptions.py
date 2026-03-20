"""Domain exception types for the quality gate module."""

from __future__ import annotations


class EvaluationError(Exception):
    """Base for all quality gate domain errors."""


class AssetNotFoundError(EvaluationError):
    """Asset does not exist."""


class SLONotConfiguredError(EvaluationError):
    """No SLO linked to asset."""


class DataSourceNotFoundError(EvaluationError):
    """Data source adapter not found."""


class DuplicateEvaluationError(EvaluationError):
    """Evaluation with same parameters already running/completed."""


class EvaluationNotFoundError(EvaluationError):
    """Evaluation ID does not exist."""
