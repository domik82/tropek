"""SLI definition models."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class SLIDefinitionCreate(BaseModel):
    """Request body for creating a new SLI definition."""

    name: str
    adapter_type: str
    display_name: str | None = None
    mode: str = 'raw'
    indicators: dict[str, str] | None = None
    query_template: str | None = None
    interval: str | None = None
    methods: list[str] | None = None
    notes: str | None = None
    author: str | None = None
    tags: dict[str, str] | None = None
    comparable_from_version: int | None = None


class SLIDefinitionRead(BaseModel):
    """SLI definition as returned by the API."""

    id: UUID
    name: str
    adapter_type: str
    display_name: str | None = None
    version: int
    comparable_from_version: int
    indicators: dict[str, str]
    notes: str | None = None
    author: str | None = None
    tags: dict[str, Any]
    mode: str
    query_template: str | None = None
    interval: str | None = None
    methods: list[str] | None = None
    active: bool
    created_at: datetime


class SliMetadata(BaseModel):
    """Metadata about SLI fetch quality (sample counts, missing data)."""

    mode: str
    expected_samples: int
    actual_samples: int
    missing_pct: float | int
    chunks_failed: int
