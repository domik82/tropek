"""Pydantic schemas for SLI definition versioned CRUD."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

from tropek.modules.common.schemas import SafeJsonAny, SafeStr, StrictInput

ALLOWED_MODES = frozenset(['raw', 'aggregated'])


class AggregationMethod(StrEnum):
    """Statistical aggregation methods available in aggregated query mode."""

    MIN = 'min'
    MEAN = 'mean'
    MAX = 'max'
    STD = 'std'
    SUM = 'sum'
    MEDIAN = 'median'
    P75 = 'p75'
    P90 = 'p90'
    P95 = 'p95'
    P99 = 'p99'


def _validate_raw_mode(sli: SLIDefinitionCreate) -> None:
    if not sli.indicators:
        msg = 'indicators must be non-empty for mode raw'
        raise ValueError(msg)
    if sli.query_template is not None:
        msg = 'query_template must not be set for mode raw'
        raise ValueError(msg)
    if sli.interval is not None:
        msg = 'interval must not be set for mode raw'
        raise ValueError(msg)
    if sli.methods is not None:
        msg = 'methods must not be set for mode raw'
        raise ValueError(msg)


def _validate_aggregated_mode(sli: SLIDefinitionCreate) -> None:
    if sli.indicators:
        msg = 'indicators must be empty for mode aggregated'
        raise ValueError(msg)
    if not sli.query_template:
        msg = 'query_template is required for mode aggregated'
        raise ValueError(msg)
    if not sli.interval:
        msg = 'interval is required for mode aggregated'
        raise ValueError(msg)
    if not sli.methods:
        msg = 'methods must be non-empty for mode aggregated'
        raise ValueError(msg)


class SLIDefinitionCreate(StrictInput):
    """Request body for creating an SLI definition."""

    name: SafeStr
    adapter_type: SafeStr
    display_name: SafeStr | None = None
    mode: SafeStr = 'raw'

    # Raw mode fields
    indicators: dict[str, str] = {}

    # Aggregated mode fields
    query_template: SafeStr | None = None
    interval: SafeStr | None = None
    methods: list[AggregationMethod] | None = None

    # Common fields
    notes: SafeStr | None = None
    author: SafeStr | None = None
    tags: SafeJsonAny = {}
    comparable_from_version: int | None = None

    @model_validator(mode='after')
    def validate_mode_fields(self) -> SLIDefinitionCreate:
        """Enforce mode-dependent field requirements."""
        if self.mode not in ALLOWED_MODES:
            msg = f'mode must be one of {sorted(ALLOWED_MODES)}, got {self.mode!r}'
            raise ValueError(msg)

        if self.mode == 'raw':
            _validate_raw_mode(self)
        elif self.mode == 'aggregated':
            _validate_aggregated_mode(self)

        return self


class SLIDefinitionRead(BaseModel):
    """Response schema for an SLI definition."""

    id: uuid.UUID
    name: str
    adapter_type: str
    display_name: str | None
    version: int
    comparable_from_version: int
    indicators: dict[str, str]
    notes: str | None
    author: str | None
    tags: dict[str, Any]
    mode: str
    query_template: str | None
    interval: str | None
    methods: list[str] | None
    active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
