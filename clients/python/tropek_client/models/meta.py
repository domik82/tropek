"""Asset metadata snapshot models."""

from uuid import UUID

from pydantic import BaseModel


class MetaValueInput(BaseModel):
    """Input for setting a metadata value at a path."""

    path: list[str]
    value: str


class MetaClosureInput(BaseModel):
    """Input for closing a metadata path."""

    path: list[str]


class MetaSnapshotCreate(BaseModel):
    """Input model for creating a metadata snapshot."""

    values: list[MetaValueInput] | None = None
    closed: list[MetaClosureInput] | None = None


class MetaSnapshotCreated(BaseModel):
    """Response after creating a metadata snapshot."""

    snapshot_id: UUID
