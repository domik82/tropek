"""Multi-source conflict resolution for the asset meta timeline pipeline."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from logging import Logger
from uuid import UUID

from .types import RawSpan

_SENTINEL_OPEN_END = datetime.max.replace(tzinfo=UTC)


def resolve_multi_source_conflicts(
    spans: list[RawSpan],
    asset_id: UUID,
    logger: Logger,
) -> list[RawSpan]:
    """Collapse multi-source conflicts to one winning source per path.

    Single-source paths pass through unchanged. Multi-source: most-recent-wins,
    losers dropped, warning logged.
    """
    spans_by_path = group_spans_by_path(spans)
    resolved: list[RawSpan] = []
    for path_key, path_spans in spans_by_path.items():
        sources_latest = compute_latest_observation_per_source(path_spans)
        if len(sources_latest) == 1:
            resolved.extend(path_spans)
            continue
        winner = pick_winning_source(sources_latest)
        log_source_conflict(logger, asset_id, path_key, sources_latest, winner)
        resolved.extend(span for span in path_spans if span.source == winner)
    return resolved


def group_spans_by_path(spans: list[RawSpan]) -> dict[tuple[str, ...], list[RawSpan]]:
    """Bucket spans by their path."""
    result: dict[tuple[str, ...], list[RawSpan]] = defaultdict(list)
    for span in spans:
        result[tuple(span.path)].append(span)
    return result


def compute_latest_observation_per_source(path_spans: list[RawSpan]) -> dict[str, datetime]:
    """For each source, the timestamp of its latest observation.

    Open spans (end=None) → sentinel future (most-current data wins).
    """
    latest: dict[str, datetime] = {}
    for span in path_spans:
        observed_at = span.end if span.end is not None else _SENTINEL_OPEN_END
        if span.source not in latest or latest[span.source] < observed_at:
            latest[span.source] = observed_at
    return latest


def pick_winning_source(sources_latest: dict[str, datetime]) -> str:
    """Primary: most recent observation. Secondary: source name alphabetical."""
    return max(sources_latest.items(), key=lambda kv: (kv[1], kv[0]))[0]


def log_source_conflict(
    logger: Logger,
    asset_id: UUID,
    path: tuple[str, ...],
    sources_latest: dict[str, datetime],
    winner: str,
) -> None:
    """Emit operator-visible warning about multi-source conflict."""
    logger.warning(
        'asset_meta_timeline.multi_source_conflict',
        extra={
            'asset_id': str(asset_id),
            'path': list(path),
            'sources': sorted(sources_latest.keys()),
            'winner': winner,
        },
    )
