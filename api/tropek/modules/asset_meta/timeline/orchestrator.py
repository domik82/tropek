"""Top-level pipeline orchestrator — composes the five derivation stages.

Pure, zero I/O. See spec §7.6 for function contract.
"""

from __future__ import annotations

from datetime import datetime
from logging import Logger
from typing import Any
from uuid import UUID

from .clipping import clip_spans
from .conflict_resolution import resolve_multi_source_conflicts
from .derivation import derive_raw_spans
from .item_emitter import build_items_wire
from .tree_builder import build_groups_wire
from .types import SnapshotWithEntries


def build_timeline_response(
    asset_id: UUID,
    snapshots: list[SnapshotWithEntries],
    window_from: datetime,
    window_to: datetime,
    logger: Logger,
) -> dict[str, list[dict[str, Any]]]:
    """Pure composition of the five derivation stages. Zero I/O."""
    raw_spans = derive_raw_spans(snapshots)
    resolved = resolve_multi_source_conflicts(raw_spans, asset_id, logger)
    clipped = clip_spans(resolved, window_from, window_to)
    return {
        'groups': build_groups_wire(clipped),
        'items': build_items_wire(clipped),
    }
