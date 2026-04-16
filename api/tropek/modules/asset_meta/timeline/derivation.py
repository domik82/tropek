"""Span derivation — walks snapshots in order and emits raw spans.

Pure, zero I/O. See spec §7.1 for function contracts.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from .types import OpenSpan, OpenSpanMap, RawSpan, SnapshotWithEntries


def is_prefix(prefix: tuple[str, ...], full: tuple[str, ...]) -> bool:
    """True if `prefix` is a prefix of `full` (including equal)."""
    return len(prefix) <= len(full) and full[: len(prefix)] == prefix


def apply_value(
    open_spans: OpenSpanMap,
    source: str,
    path: tuple[str, ...],
    value: str,
    observed_at: datetime,
    emitted: list[RawSpan],
) -> None:
    """Record one observation of (source, path) = value at observed_at.

    - If no span is currently open for (source, path), open one.
    - If an open span has the same value, the span continues unchanged (no-op).
    - If an open span has a different value, close it at observed_at and open a new one.
    """
    key = (source, path)
    existing = open_spans.get(key)
    if existing is None:
        open_spans[key] = OpenSpan(value=value, span_start=observed_at)
        return
    if existing.value == value:
        return
    emitted.append(
        RawSpan(
            source=source,
            path=list(path),
            value=existing.value,
            start=existing.span_start,
            end=observed_at,
            end_reason='value_change',
        )
    )
    open_spans[key] = OpenSpan(value=value, span_start=observed_at)


def close_cascade(
    open_spans: OpenSpanMap,
    source: str,
    ancestor: tuple[str, ...],
    closed_at: datetime,
    emitted: list[RawSpan],
) -> None:
    """Close open span for `ancestor` AND every currently-open descendant for same source.

    Idempotent: if no open span matches, this is a silent no-op.
    """
    keys_to_close = [
        key
        for key in open_spans
        if key[0] == source and is_prefix(ancestor, key[1])
    ]
    for key in keys_to_close:
        open_span = open_spans.pop(key)
        emitted.append(
            RawSpan(
                source=key[0],
                path=list(key[1]),
                value=open_span.value,
                start=open_span.span_start,
                end=closed_at,
                end_reason='closed',
            )
        )


def apply_snapshot(
    open_spans: OpenSpanMap,
    snapshot: SnapshotWithEntries,
    emitted: list[RawSpan],
) -> None:
    """Apply one snapshot. Closures run BEFORE values (close-and-reopen determinism)."""
    for closure_path in snapshot.closures:
        close_cascade(
            open_spans, snapshot.source, tuple(closure_path), snapshot.observed_at, emitted
        )
    for path, value in snapshot.values:
        apply_value(open_spans, snapshot.source, tuple(path), value, snapshot.observed_at, emitted)


def finalize_open_spans(open_spans: OpenSpanMap, emitted: list[RawSpan]) -> None:
    """After all snapshots processed, emit remaining open spans with end=None."""
    for (source, path_tuple), open_span in open_spans.items():
        emitted.append(
            RawSpan(
                source=source,
                path=list(path_tuple),
                value=open_span.value,
                start=open_span.span_start,
                end=None,
                end_reason='open',
            )
        )


def derive_raw_spans(snapshots: Iterable[SnapshotWithEntries]) -> list[RawSpan]:
    """Top-level entry point. Walks snapshots in order and emits raw spans. Pure, zero I/O."""
    open_spans: OpenSpanMap = {}
    emitted: list[RawSpan] = []
    for snapshot in snapshots:
        apply_snapshot(open_spans, snapshot, emitted)
    finalize_open_spans(open_spans, emitted)
    return emitted
