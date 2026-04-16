"""Pydantic schemas for the asset meta timeline ingest and read APIs."""

from __future__ import annotations

from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from tropek.modules.common.schemas import StrictInput

MAX_PATH_ENTRY_LENGTH = 128


class MetaValueInput(StrictInput):
    """A single key-value pair to set in the metadata timeline."""

    path: list[str] = Field(min_length=1, max_length=6)
    value: str = Field(max_length=1024)

    @field_validator('path')
    @classmethod
    def _validate_path_entries(cls, entries: list[str]) -> list[str]:
        for entry in entries:
            if not 1 <= len(entry) <= MAX_PATH_ENTRY_LENGTH:
                raise ValueError('path entries must be 1-128 characters')
        return entries


class MetaClosureInput(StrictInput):
    """A path to close (end its current span) in the metadata timeline."""

    path: list[str] = Field(min_length=1, max_length=6)

    @field_validator('path')
    @classmethod
    def _validate_path_entries(cls, entries: list[str]) -> list[str]:
        for entry in entries:
            if not 1 <= len(entry) <= MAX_PATH_ENTRY_LENGTH:
                raise ValueError('path entries must be 1-128 characters')
        return entries


class MetaSnapshotCreate(StrictInput):
    """Request body for creating a metadata snapshot."""

    source: str = Field(min_length=1, max_length=64, pattern=r'^[a-zA-Z0-9._-]+$')
    observed_at: AwareDatetime
    values: list[MetaValueInput] = Field(default_factory=list, max_length=10_000)
    closed: list[MetaClosureInput] = Field(default_factory=list, max_length=1_000)

    @field_validator('values')
    @classmethod
    def _unique_value_paths(cls, entries: list[MetaValueInput]) -> list[MetaValueInput]:
        seen: set[tuple[str, ...]] = set()
        for entry in entries:
            path_key = tuple(entry.path)
            if path_key in seen:
                raise ValueError(f'duplicate path in values: {entry.path}')
            seen.add(path_key)
        return entries

    @field_validator('closed')
    @classmethod
    def _unique_closed_paths(cls, entries: list[MetaClosureInput]) -> list[MetaClosureInput]:
        seen: set[tuple[str, ...]] = set()
        for entry in entries:
            path_key = tuple(entry.path)
            if path_key in seen:
                raise ValueError(f'duplicate path in closed: {entry.path}')
            seen.add(path_key)
        return entries


class MetaSnapshotCreated(BaseModel):
    """Response body after creating a metadata snapshot."""

    snapshot_id: UUID


# --- Read-side response models (consumed by Chunk 4) ---


class TimelineGroup(BaseModel):
    """A group in the vis-timeline visualization."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    content: str
    nested_groups: list[str] | None = Field(default=None, alias='nestedGroups')
    show_nested: bool | None = Field(default=None, alias='showNested')


class TimelineItem(BaseModel):
    """A single item (span) in the vis-timeline visualization."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    group: str
    content: str
    start: str
    end: str
    type: str
    class_name: str = Field(alias='className')
    source: str


class TimelineResponse(BaseModel):
    """Full timeline response with groups and items."""

    groups: list[TimelineGroup]
    items: list[TimelineItem]


class TimelineSummaryResponse(BaseModel):
    """Summary statistics for the timeline."""

    model_config = ConfigDict(populate_by_name=True)

    item_count: int = Field(alias='itemCount')
