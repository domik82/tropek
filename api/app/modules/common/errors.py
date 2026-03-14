"""Shared HTTP error helpers."""

from __future__ import annotations

from typing import NoReturn

from fastapi import HTTPException


def raise_not_found(entity: str, name: str) -> NoReturn:
    """Raise 404 with a consistent message format."""
    raise HTTPException(status_code=404, detail=f"{entity} '{name}' not found")


def raise_conflict(entity: str, name: str, reason: str = "already exists") -> NoReturn:
    """Raise 409 with a consistent message format."""
    raise HTTPException(status_code=409, detail=f"{entity} '{name}' {reason}")
