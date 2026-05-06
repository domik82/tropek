from datetime import UTC, datetime

from tropek.modules.asset_meta.timeline.summary import count_distinct_leaf_paths
from tropek.modules.asset_meta.timeline.types import ClippedSpan


def make_clipped(path):
    return ClippedSpan(
        source='cicd',
        label_path=path,
        value='1.0',
        start=datetime(2026, 4, 1, tzinfo=UTC),
        end=datetime(2026, 4, 30, tzinfo=UTC),
        className='meta-span',
    )


def test_count_distinct_leaf_paths_deduplicates():
    spans = [
        make_clipped(['app-A']),
        make_clipped(['cpu-cores']),
        make_clipped(['cpu-cores']),
    ]
    assert count_distinct_leaf_paths(spans) == 2


def test_count_distinct_leaf_paths_empty():
    assert count_distinct_leaf_paths([]) == 0
