"""Pydantic parameter models for SLI registry repository methods."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SLICreateParams(BaseModel):
    """Parameters for SLIRepository.create()."""

    name: str
    indicators: dict[str, str]
    adapter_type: str
    display_name: str | None = None
    notes: str | None = None
    author: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)
    comparable_from_version: int | None = None
    mode: str = 'raw'
    query_template: str | None = None
    interval: str | None = None
    methods: list[str] | None = None
