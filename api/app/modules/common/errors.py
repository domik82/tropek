"""Convenience error helpers for common HTTP responses."""

from __future__ import annotations

from typing import NoReturn

from app.modules.common.exceptions import NotFoundError


def raise_not_found(entity: str, name: str) -> NoReturn:
    """Raise a NotFoundError for the given entity and name.

    Handled globally by the app's exception handler and converted to a 404 response.

    Args:
        entity: Entity type name (e.g. "slo group", "asset").
        name: Entity identifier.

    Raises:
        NotFoundError: Always.
    """
    raise NotFoundError(entity, name)
