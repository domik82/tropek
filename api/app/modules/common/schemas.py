"""Shared Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel


class PagedResponse[T](BaseModel):
    """Generic paginated list response."""

    items: list[T]
    total: int
