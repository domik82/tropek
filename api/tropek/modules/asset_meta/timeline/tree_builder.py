"""Group hierarchy builder for vis-timeline (§7.4)."""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from .types import ClippedSpan


def encode_path_as_group_id(path: tuple[str, ...]) -> str:
    """Single point of truth for path → vis-timeline group id encoding."""
    return json.dumps(list(path), ensure_ascii=False, separators=(',', ':'))


def collect_distinct_paths(spans: list[ClippedSpan]) -> set[tuple[str, ...]]:
    """Extract the set of distinct path tuples present in the clipped spans."""
    return {tuple(span.label_path) for span in spans}


def expand_with_synthetic_ancestors(paths: set[tuple[str, ...]]) -> set[tuple[str, ...]]:
    """Return paths plus every ancestor prefix.

    E.g. if only leaf is ("app-A", "pkg-1", "alpha"), result includes
    ("app-A",), ("app-A", "pkg-1"), and ("app-A", "pkg-1", "alpha").
    """
    expanded: set[tuple[str, ...]] = set()
    for path in paths:
        for length in range(1, len(path) + 1):
            expanded.add(path[:length])
    return expanded


def compute_children_map(
    paths: set[tuple[str, ...]],
) -> dict[tuple[str, ...], list[tuple[str, ...]]]:
    """Build parent → immediate-children map."""
    result: dict[tuple[str, ...], list[tuple[str, ...]]] = defaultdict(list)
    for path in paths:
        if len(path) > 1:
            result[path[:-1]].append(path)
    return result


def sort_groups_deterministically(paths: set[tuple[str, ...]]) -> list[tuple[str, ...]]:
    """Primary: depth ASC (roots first). Secondary: path lexicographically."""
    return sorted(paths, key=lambda path: (len(path), path))


def build_group_entry(
    path: tuple[str, ...],
    children_map: dict[tuple[str, ...], list[tuple[str, ...]]],
) -> dict[str, Any]:
    """Build one group dict. Adds nestedGroups/showNested iff path has children."""
    entry: dict[str, Any] = {
        'id': encode_path_as_group_id(path),
        'content': path[-1],
    }
    if path in children_map:
        children_sorted = sorted(children_map[path])
        entry['nestedGroups'] = [encode_path_as_group_id(child) for child in children_sorted]
        entry['showNested'] = False
    return entry


def build_groups_wire(clipped_spans: list[ClippedSpan]) -> list[dict[str, Any]]:
    """Build vis-timeline groups list. Synthesizes intermediate ancestors."""
    distinct_paths = collect_distinct_paths(clipped_spans)
    all_group_paths = expand_with_synthetic_ancestors(distinct_paths)
    children_map = compute_children_map(all_group_paths)
    return [build_group_entry(path, children_map) for path in sort_groups_deterministically(all_group_paths)]
