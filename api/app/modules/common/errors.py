"""Shared HTTP error helpers."""

from __future__ import annotations

from fastapi import HTTPException


def raise_not_found(entity: str, name: str) -> None:
    """Raise 404 with a consistent message format."""
    raise HTTPException(status_code=404, detail=f"{entity} '{name}' not found")


def raise_conflict(entity: str, name: str, reason: str = "already exists") -> None:
    """Raise 409 with a consistent message format."""
    raise HTTPException(status_code=409, detail=f"{entity} '{name}' {reason}")
