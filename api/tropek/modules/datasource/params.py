"""Pydantic parameter models for DataSource repository methods."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from tropek.modules.common.schemas import StrictInput


class DataSourceCreateParams(StrictInput):
    """Parameters for DataSourceRepository.create()."""

    name: str
    adapter_type: str
    adapter_url: str
    display_name: str | None = None
    tags: dict[str, Any] = Field(default_factory=dict)
    token: str | None = None
