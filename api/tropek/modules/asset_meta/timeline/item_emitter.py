"""vis-timeline item emitter (§7.5) — converts ClippedSpans to wire-format item dicts."""

from __future__ import annotations

from .tree_builder import encode_path_as_group_id
from .types import ClippedSpan


def build_items_wire(spans: list[ClippedSpan]) -> list[dict]:
    """Convert clipped spans to vis-timeline items. One-to-one transform."""
    return [item_from_span(span, index) for index, span in enumerate(spans)]


def item_from_span(span: ClippedSpan, index: int) -> dict:
    """Build one vis-timeline item dict from a clipped span."""
    return {
        'id': f's{index}',
        'group': encode_path_as_group_id(tuple(span.path)),
        'content': span.value,
        'start': span.start.isoformat(),
        'end': span.end.isoformat(),
        'type': 'range',
        'className': span.className,
        'source': span.source,
    }
