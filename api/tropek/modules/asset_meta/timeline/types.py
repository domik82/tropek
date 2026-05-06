"""Immutable data types for the asset meta timeline pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True)
class RawSpan:
    """A single continuous span of a metadata value from one snapshot source."""

    source: str
    label_path: list[str]
    value: str
    start: datetime
    end: datetime | None
    end_reason: Literal['value_change', 'closed', 'open']


@dataclass(frozen=True)
class ClippedSpan:
    """A RawSpan clipped to a query window, ready for vis-timeline rendering."""

    source: str
    label_path: list[str]
    value: str
    start: datetime
    end: datetime
    className: str  # noqa: N815 — matches vis-timeline's wire format field name


@dataclass(frozen=True)
class OpenSpan:
    """A span that has not yet been closed within the current accumulation window."""

    value: str
    span_start: datetime


@dataclass(frozen=True)
class SnapshotWithEntries:
    """A parsed snapshot record with its key-value entries and explicit closures."""

    source: str
    observed_at: datetime
    values: list[tuple[list[str], str]]
    closures: list[list[str]]


OpenSpanMap = dict[tuple[str, tuple[str, ...]], OpenSpan]
"""Keyed by (source, path_tuple); tracks spans still open at the accumulation cursor."""
