"""Pagination types for API responses."""

from pydantic import BaseModel


class PagedResponse[T](BaseModel):
    """Generic paginated response container."""

    items: list[T]
    total: int
