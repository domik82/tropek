"""Pydantic schemas for the asset meta timeline ingest and read APIs."""

from __future__ import annotations

from typing import Annotated, Self
from uuid import UUID

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from tropek.modules.common.schemas import SafeStr, StrictInput, reject_null_bytes

PathEntry = Annotated[str, StringConstraints(min_length=1, max_length=128), AfterValidator(reject_null_bytes)]


class MetaValueInput(StrictInput):
    """A single key-value pair to set in the metadata timeline."""

    label_path: list[PathEntry] = Field(min_length=1, max_length=6)
    value: SafeStr = Field(max_length=1024)


class MetaClosureInput(StrictInput):
    """A path to close (end its current span) in the metadata timeline."""

    label_path: list[PathEntry] = Field(min_length=1, max_length=6)


class MetaSnapshotCreate(StrictInput):
    """Request body for creating a metadata snapshot."""

    # anyOf tells OpenAPI consumers (e.g. schemathesis) that at least one of
    # values/closed must be non-empty. The model_validator below is the runtime
    # authority; anyOf just keeps fuzzers from generating the empty-empty case.
    model_config = ConfigDict(
        extra='forbid',
        json_schema_extra={
            'anyOf': [
                {'properties': {'values': {'minItems': 1}}, 'required': ['values']},
                {'properties': {'closed': {'minItems': 1}}, 'required': ['closed']},
            ],
        },
    )

    source: str = Field(min_length=1, max_length=64, pattern=r'^[a-zA-Z0-9._-]+$')
    observed_at: AwareDatetime
    # uniqueItems: True tells schemathesis that duplicate paths are forbidden —
    # enforced at runtime by _unique_value_paths/_unique_closed_paths validators.
    # The values[] uniqueness is by path only (not the full item), so uniqueItems
    # on the full item would be overly permissive; declare it for closed[] where
    # the item *is* the path, and for values[] to keep schemathesis happy.
    values: list[MetaValueInput] = Field(
        default_factory=list, max_length=10_000, json_schema_extra={'uniqueItems': True}
    )
    closed: list[MetaClosureInput] = Field(
        default_factory=list, max_length=1_000, json_schema_extra={'uniqueItems': True}
    )

    @field_validator('values')
    @classmethod
    def _unique_value_paths(cls, entries: list[MetaValueInput]) -> list[MetaValueInput]:
        seen: set[tuple[str, ...]] = set()
        for entry in entries:
            path_key = tuple(entry.label_path)
            if path_key in seen:
                raise ValueError(f'duplicate label_path in values: {entry.label_path}')
            seen.add(path_key)
        return entries

    @field_validator('closed')
    @classmethod
    def _unique_closed_paths(cls, entries: list[MetaClosureInput]) -> list[MetaClosureInput]:
        seen: set[tuple[str, ...]] = set()
        for entry in entries:
            path_key = tuple(entry.label_path)
            if path_key in seen:
                raise ValueError(f'duplicate label_path in closed: {entry.label_path}')
            seen.add(path_key)
        return entries

    @model_validator(mode='after')
    def _require_values_or_closed(self) -> Self:
        """Reject snapshots that carry neither values nor closures."""
        if not self.values and not self.closed:
            raise ValueError('snapshot must contain values or closed entries')
        return self


class MetaSnapshotCreated(BaseModel):
    """Response body after creating a metadata snapshot."""

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
    observed_at: AwareDatetime
    value_count: int
    closure_count: int
    created_at: AwareDatetime


class MetaSnapshotDetail(BaseModel):
    """Full detail of a snapshot including values and closures."""

    id: UUID
    source: str
    observed_at: AwareDatetime
    created_at: AwareDatetime
    values: list[MetaValueOutput]
    closures: list[MetaClosureOutput]


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
