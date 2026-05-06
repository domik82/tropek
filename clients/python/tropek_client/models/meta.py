"""Asset metadata snapshot models."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class MetaValueInput(BaseModel):
    """Input for setting a metadata value at a label path."""

    label_path: list[str]
    value: str


class MetaClosureInput(BaseModel):
    """Input for closing a metadata label path."""

    label_path: list[str]


class MetaSnapshotCreate(BaseModel):
    """Input model for creating a metadata snapshot."""

    source: str
    observed_at: str
    values: list[MetaValueInput] | None = None
    closed: list[MetaClosureInput] | None = None


class MetaSnapshotCreated(BaseModel):
    """Response after creating a metadata snapshot."""

    snapshot_id: UUID


class MetaValueOutput(BaseModel):
    """A value entry in a snapshot detail response."""

    label_path: list[str]
    value: str


class MetaClosureOutput(BaseModel):
    """A closure entry in a snapshot detail response."""

    label_path: list[str]


class MetaSnapshotSummary(BaseModel):
    """Summary of a snapshot for list responses."""

    id: UUID
    source: str
    observed_at: datetime
    value_count: int
    closure_count: int
    created_at: datetime


class MetaSnapshotDetail(BaseModel):
    """Full detail of a snapshot including values and closures."""

    id: UUID
    source: str
    observed_at: datetime
    created_at: datetime
    values: list[MetaValueOutput]
    closures: list[MetaClosureOutput]
