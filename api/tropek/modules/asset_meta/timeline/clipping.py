"""Window clipping for the asset meta timeline pipeline.

Implements §7.3: clip raw spans to a caller-supplied [window_from, window_to] interval
and annotate them with CSS class names for vis-timeline rendering.
"""

from __future__ import annotations

from datetime import datetime

from .types import ClippedSpan, RawSpan


def clip_spans(
    spans: list[RawSpan],
    window_from: datetime,
    window_to: datetime,
) -> list[ClippedSpan]:
    """Clip every span to [window_from, window_to], drop ones outside."""
    return [clipped for span in spans if (clipped := clip_one_span(span, window_from, window_to)) is not None]


def clip_one_span(
    span: RawSpan,
    window_from: datetime,
    window_to: datetime,
) -> ClippedSpan | None:
    """Clip a single span. Return None if entirely outside."""
    effective_end = span.end if span.end is not None else window_to
    if effective_end <= window_from:
        return None  # entirely before window
    if span.start >= window_to:
        return None  # entirely after window

    clipped_start = max(span.start, window_from)
    clipped_end = min(effective_end, window_to)
    classes = compute_span_classes(
        span=span,
        window_from=window_from,
        window_to=window_to,
        clipped_start=clipped_start,
    )
    return ClippedSpan(
        source=span.source,
        label_path=span.label_path,
        value=span.value,
        start=clipped_start,
        end=clipped_end,
        className=' '.join(classes),
    )


def compute_span_classes(
    span: RawSpan,
    window_from: datetime,
    window_to: datetime,
    clipped_start: datetime,
) -> list[str]:
    """Compute CSS class list based on how span sits in window.

    Class vocabulary:
    - meta-span: base class on every span
    - meta-span-clipped-left: span started before window_from
    - meta-span-open: span.end is None (still open)
    - meta-span-clipped-right: span.end > window_to (continues past window)
    - meta-span-closed: span was explicitly terminated (end_reason == "closed")
    """
    classes = ['meta-span']
    if clipped_start > span.start:
        classes.append('meta-span-clipped-left')
    if span.end is None:
        classes.append('meta-span-open')
    elif span.end > window_to:
        classes.append('meta-span-clipped-right')
    if span.end_reason == 'closed':
        classes.append('meta-span-closed')
    return classes
