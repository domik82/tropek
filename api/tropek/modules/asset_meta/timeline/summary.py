"""Summary statistics for the asset meta timeline pipeline."""

from __future__ import annotations

from .types import ClippedSpan


def count_distinct_leaf_paths(spans: list[ClippedSpan]) -> int:
    """Count distinct paths present in the clipped spans."""
    return len({tuple(span.path) for span in spans})
