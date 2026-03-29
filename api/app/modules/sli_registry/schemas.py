"""Pydantic schemas for SLI definition versioned CRUD."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

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


class SLIDefinitionCreate(BaseModel):
    """Request body for creating an SLI definition."""

    name: str
    adapter_type: str
    display_name: str | None = None
    mode: str = 'raw'

    # Raw mode fields
    indicators: dict[str, str] = {}

    # Aggregated mode fields
    query_template: str | None = None
    interval: str | None = None
    methods: list[AggregationMethod] | None = None

    # Common fields
    notes: str | None = None
    author: str | None = None
    tags: dict[str, Any] = {}
    comparable_from_version: int | None = None

    @model_validator(mode='after')
    def validate_mode_fields(self) -> SLIDefinitionCreate:
        """Enforce mode-dependent field requirements."""
        if self.mode not in ALLOWED_MODES:
            msg = f'mode must be one of {sorted(ALLOWED_MODES)}, got {self.mode!r}'
            raise ValueError(msg)

        if self.mode == 'raw':
            if not self.indicators:
                msg = 'indicators must be non-empty for mode raw'
                raise ValueError(msg)
            if self.query_template is not None:
                msg = 'query_template must not be set for mode raw'
                raise ValueError(msg)
            if self.interval is not None:
                msg = 'interval must not be set for mode raw'
                raise ValueError(msg)
            if self.methods is not None:
                msg = 'methods must not be set for mode raw'
                raise ValueError(msg)

        elif self.mode == 'aggregated':
            if self.indicators:
                msg = 'indicators must be empty for mode aggregated'
                raise ValueError(msg)
            if not self.query_template:
                msg = 'query_template is required for mode aggregated'
                raise ValueError(msg)
            if not self.interval:
                msg = 'interval is required for mode aggregated'
                raise ValueError(msg)
            if not self.methods:
                msg = 'methods must be non-empty for mode aggregated'
                raise ValueError(msg)

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
