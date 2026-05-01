"""End-to-end orchestrator tests — §10.1 scenarios 1-19.

Scenarios 1-3, 9, 19 are also tested at the derivation layer in test_derivation.py;
here they are tested end-to-end through the full pipeline including clipping and item emission.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from tropek.modules.asset_meta.timeline.orchestrator import build_timeline_response
from tropek.modules.asset_meta.timeline.types import SnapshotWithEntries

ASSET_ID = uuid.uuid4()
LOGGER = logging.getLogger('test')
T0 = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC)
T1 = T0 + timedelta(days=1)
T2 = T0 + timedelta(days=2)
T3 = T0 + timedelta(days=3)
WINDOW_FROM = T0 - timedelta(days=30)
WINDOW_TO = T0 + timedelta(days=30)


def snap(
    source: str = 'cicd',
    observed_at: datetime = T0,
    values: list[tuple[list[str], str]] | None = None,
    closures: list[list[str]] | None = None,
) -> SnapshotWithEntries:
    return SnapshotWithEntries(
        source=source,
        observed_at=observed_at,
        values=values or [],
        closures=closures or [],
    )


def build(snapshots: list[SnapshotWithEntries]) -> dict:
    return build_timeline_response(ASSET_ID, snapshots, WINDOW_FROM, WINDOW_TO, LOGGER)


# ---------------------------------------------------------------------------
# Scenario 1: Single snapshot with one value
# ---------------------------------------------------------------------------


class TestScenario01SingleValue:
    def test_one_group_one_item(self) -> None:
        result = build([snap(values=[(['app'], 'v1')])])

        assert len(result['groups']) == 1
        assert len(result['items']) == 1

    def test_open_span_class(self) -> None:
        result = build([snap(values=[(['app'], 'v1')])])
        item = result['items'][0]

        assert 'meta-span' in item['className']
        assert 'meta-span-open' in item['className']


# ---------------------------------------------------------------------------
# Scenario 2: Two snapshots identical value → one long span
# ---------------------------------------------------------------------------


class TestScenario02IdenticalValues:
    def test_collapses_to_one_item(self) -> None:
        result = build(
            [
                snap(observed_at=T0, values=[(['app'], 'v1')]),
                snap(observed_at=T1, values=[(['app'], 'v1')]),
            ]
        )

        assert len(result['items']) == 1


# ---------------------------------------------------------------------------
# Scenario 3: Two snapshots different values same path → two back-to-back spans
# ---------------------------------------------------------------------------


class TestScenario03DifferentValues:
    def test_two_items(self) -> None:
        result = build(
            [
                snap(observed_at=T0, values=[(['app'], 'v1')]),
                snap(observed_at=T1, values=[(['app'], 'v2')]),
            ]
        )

        assert len(result['items']) == 2

    def test_first_has_end_reason_style(self) -> None:
        result = build(
            [
                snap(observed_at=T0, values=[(['app'], 'v1')]),
                snap(observed_at=T1, values=[(['app'], 'v2')]),
            ]
        )
        first_item = next(item for item in result['items'] if item['content'] == 'v1')
        second_item = next(item for item in result['items'] if item['content'] == 'v2')

        assert 'meta-span-open' not in first_item['className']
        assert 'meta-span-open' in second_item['className']


# ---------------------------------------------------------------------------
# Scenario 4: Explicit closure
# ---------------------------------------------------------------------------


class TestScenario04ExplicitClosure:
    def test_closed_class(self) -> None:
        result = build(
            [
                snap(observed_at=T0, values=[(['app'], 'v1')]),
                snap(observed_at=T1, closures=[['app']]),
            ]
        )

        assert len(result['items']) == 1
        assert 'meta-span-closed' in result['items'][0]['className']


# ---------------------------------------------------------------------------
# Scenario 5: Cascading closure
# ---------------------------------------------------------------------------


class TestScenario05CascadingClosure:
    def test_three_items_all_closed(self) -> None:
        result = build(
            [
                snap(
                    observed_at=T0,
                    values=[
                        (['app'], 'v1'),
                        (['app', 'plug-1'], 'p1'),
                        (['app', 'plug-2'], 'p2'),
                    ],
                ),
                snap(observed_at=T1, closures=[['app']]),
            ]
        )

        assert len(result['items']) == 3
        for item in result['items']:
            assert 'meta-span-closed' in item['className']


# ---------------------------------------------------------------------------
# Scenario 6: Cascading closure is source-scoped
# ---------------------------------------------------------------------------


class TestScenario06CascadingClosureSourceScoped:
    def test_other_source_span_still_open(self) -> None:
        result = build(
            [
                snap(source='source-a', observed_at=T0, values=[(['app'], 'v1')]),
                snap(source='source-b', observed_at=T0, values=[(['app'], 'b1')]),
                snap(source='source-a', observed_at=T1, closures=[['app']]),
            ]
        )

        # Conflict resolution keeps only the winner for path ['app'].
        # source-a has an explicit closure (ends at T1), source-b has an open span.
        # Most-recent-wins: source-b's open span uses sentinel future → source-b wins.
        # So only source-b items survive, and it should be open.
        items = result['items']
        assert len(items) == 1
        assert items[0]['source'] == 'source-b'
        assert 'meta-span-open' in items[0]['className']


# ---------------------------------------------------------------------------
# Scenario 7: Close-and-reopen
# ---------------------------------------------------------------------------


class TestScenario07CloseAndReopen:
    def test_two_items_for_path(self) -> None:
        result = build(
            [
                snap(observed_at=T0, values=[(['foo'], 'old')]),
                snap(observed_at=T1, closures=[['foo']], values=[(['foo'], 'new')]),
            ]
        )

        foo_items = [item for item in result['items'] if item['content'] in ('old', 'new')]
        assert len(foo_items) == 2

    def test_first_closed_second_open(self) -> None:
        result = build(
            [
                snap(observed_at=T0, values=[(['foo'], 'old')]),
                snap(observed_at=T1, closures=[['foo']], values=[(['foo'], 'new')]),
            ]
        )

        old_item = next(item for item in result['items'] if item['content'] == 'old')
        new_item = next(item for item in result['items'] if item['content'] == 'new')

        assert 'meta-span-closed' in old_item['className']
        assert 'meta-span-open' in new_item['className']


# ---------------------------------------------------------------------------
# Scenario 8: Collection-gap — source A's span is one continuous span
# ---------------------------------------------------------------------------


class TestScenario08CollectionGap:
    def test_source_a_one_continuous_span(self) -> None:
        result = build(
            [
                snap(source='source-a', observed_at=T0, values=[(['svc'], 'v1')]),
                snap(source='source-b', observed_at=T1, values=[(['other'], 'b1')]),
                snap(source='source-a', observed_at=T2, values=[(['svc'], 'v1')]),
            ]
        )

        source_a_items = [item for item in result['items'] if item['source'] == 'source-a']
        assert len(source_a_items) == 1


# ---------------------------------------------------------------------------
# Scenario 9: Daily heartbeat — 30 identical snapshots → 1 item
# ---------------------------------------------------------------------------


class TestScenario09DailyHeartbeat:
    def test_collapses_to_one_item(self) -> None:
        snapshots = [snap(observed_at=T0 + timedelta(days=day), values=[(['app'], 'v1')]) for day in range(30)]
        result = build(snapshots)

        assert len(result['items']) == 1


# ---------------------------------------------------------------------------
# Scenario 10: Multi-source conflict — most-recent-wins, warning logged
# ---------------------------------------------------------------------------


class TestScenario10MultiSourceConflict:
    def test_only_winner_items(self) -> None:
        # Both sources produce open spans (end=None → sentinel future).
        # Tiebreaker: alphabetical max → 'source-b' > 'source-a' → source-b wins.
        result = build(
            [
                snap(source='source-a', observed_at=T0, values=[(['app'], 'old')]),
                snap(source='source-b', observed_at=T1, values=[(['app'], 'new')]),
            ]
        )

        for item in result['items']:
            assert item['source'] == 'source-b'

    def test_warning_logged(self, caplog: logging.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING, logger='test.conflict'):
            conflict_logger = logging.getLogger('test.conflict')
            build_timeline_response(
                ASSET_ID,
                [
                    snap(source='source-a', observed_at=T0, values=[(['app'], 'old')]),
                    snap(source='source-b', observed_at=T1, values=[(['app'], 'new')]),
                ],
                WINDOW_FROM,
                WINDOW_TO,
                conflict_logger,
            )

        assert any('multi_source_conflict' in record.message for record in caplog.records)


# ---------------------------------------------------------------------------
# Scenario 11: Synthetic intermediates
# ---------------------------------------------------------------------------


class TestScenario11SyntheticIntermediates:
    def test_three_groups_from_leaf_only(self) -> None:
        result = build(
            [
                snap(values=[(['app-A', 'plug-1', 'alpha'], 'v1')]),
            ]
        )

        assert len(result['groups']) == 3
        group_contents = [group['content'] for group in result['groups']]
        assert 'app-A' in group_contents
        assert 'plug-1' in group_contents
        assert 'alpha' in group_contents


# ---------------------------------------------------------------------------
# Scenario 12: Left-edge clipping
# ---------------------------------------------------------------------------


class TestScenario12LeftEdgeClipping:
    def test_clipped_left_class(self) -> None:
        early_start = WINDOW_FROM - timedelta(days=10)
        result = build_timeline_response(
            ASSET_ID,
            [snap(observed_at=early_start, values=[(['app'], 'v1')])],
            WINDOW_FROM,
            WINDOW_TO,
            LOGGER,
        )

        assert len(result['items']) == 1
        assert 'meta-span-clipped-left' in result['items'][0]['className']


# ---------------------------------------------------------------------------
# Scenario 13: Right-edge clipping — three sub-cases
# ---------------------------------------------------------------------------


class TestScenario13RightEdgeClipping:
    def test_open_span_gets_open_class(self) -> None:
        """Open span (end=None) → 'meta-span-open'."""
        result = build([snap(values=[(['app'], 'v1')])])

        assert 'meta-span-open' in result['items'][0]['className']

    def test_span_ending_after_window_gets_clipped_right(self) -> None:
        """Span ends after window_to → 'meta-span-clipped-right'."""
        far_future_close = WINDOW_TO + timedelta(days=10)
        result = build_timeline_response(
            ASSET_ID,
            [
                snap(observed_at=T0, values=[(['app'], 'v1')]),
                snap(observed_at=far_future_close, values=[(['app'], 'v2')]),
            ],
            WINDOW_FROM,
            WINDOW_TO,
            LOGGER,
        )

        # The first span [T0, far_future_close] has end > WINDOW_TO → clipped-right
        first_item = next(item for item in result['items'] if item['content'] == 'v1')
        assert 'meta-span-clipped-right' in first_item['className']

    def test_span_closed_within_window_gets_closed_class(self) -> None:
        """Span ends within window with closure → 'meta-span-closed'."""
        result = build(
            [
                snap(observed_at=T0, values=[(['app'], 'v1')]),
                snap(observed_at=T1, closures=[['app']]),
            ]
        )

        assert 'meta-span-closed' in result['items'][0]['className']


# ---------------------------------------------------------------------------
# Scenario 14: Empty asset
# ---------------------------------------------------------------------------


class TestScenario14EmptyAsset:
    def test_empty_result(self) -> None:
        result = build([])

        assert result == {'groups': [], 'items': []}


# ---------------------------------------------------------------------------
# Scenario 15: Validation-layer (Pydantic), not derivation. No test needed here.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Scenario 16: Closed-only snapshot terminates existing span
# ---------------------------------------------------------------------------


class TestScenario16ClosedOnlyTerminates:
    def test_one_item_closed(self) -> None:
        result = build(
            [
                snap(observed_at=T0, values=[(['legacy'], 'v1')]),
                snap(observed_at=T1, closures=[['legacy']]),
            ]
        )

        assert len(result['items']) == 1
        assert 'meta-span-closed' in result['items'][0]['className']


# ---------------------------------------------------------------------------
# Scenario 17: Closed-only targeting already-closed path is no-op
# ---------------------------------------------------------------------------


class TestScenario17DoubleClose:
    def test_exactly_one_item(self) -> None:
        result = build(
            [
                snap(observed_at=T0, values=[(['foo'], 'v1')]),
                snap(observed_at=T1, closures=[['foo']]),
                snap(observed_at=T2, closures=[['foo']]),
            ]
        )

        assert len(result['items']) == 1
        # The span should run from T0 to T1
        item = result['items'][0]
        assert item['start'] == T0.isoformat()
        assert item['end'] == T1.isoformat()


# ---------------------------------------------------------------------------
# Scenario 18: Closed-only targeting never-opened path is no-op
# ---------------------------------------------------------------------------


class TestScenario18CloseNeverOpened:
    def test_zero_items(self) -> None:
        result = build([snap(closures=[['never-existed']])])

        assert len(result['items']) == 0
        assert len(result['groups']) == 0


# ---------------------------------------------------------------------------
# Scenario 19: Closed-only cascading (via closed-only snapshot, values=[])
# ---------------------------------------------------------------------------


class TestScenario19ClosedOnlyCascading:
    def test_three_items_all_closed_at_t1(self) -> None:
        result = build(
            [
                snap(
                    observed_at=T0,
                    values=[
                        (['app'], 'v1'),
                        (['app', 'plug-1'], 'p1'),
                        (['app', 'plug-2'], 'p2'),
                    ],
                ),
                snap(observed_at=T1, values=[], closures=[['app']]),
            ]
        )

        assert len(result['items']) == 3
        for item in result['items']:
            assert 'meta-span-closed' in item['className']
            assert item['end'] == T1.isoformat()
