from datetime import UTC, datetime, timedelta

from tropek.modules.asset_meta.timeline.derivation import (
    apply_snapshot,
    apply_value,
    close_cascade,
    derive_raw_spans,
    finalize_open_spans,
    is_prefix,
)
from tropek.modules.asset_meta.timeline.types import (
    OpenSpan,
    OpenSpanMap,
    RawSpan,
    SnapshotWithEntries,
)

T0 = datetime(2026, 4, 16, 10, 0, 0, tzinfo=UTC)
T1 = T0 + timedelta(hours=1)
T2 = T0 + timedelta(hours=2)


# ---------------------------------------------------------------------------
# is_prefix
# ---------------------------------------------------------------------------


class TestIsPrefix:
    def test_equal_tuples(self) -> None:
        assert is_prefix(('a', 'b'), ('a', 'b')) is True

    def test_strict_prefix(self) -> None:
        assert is_prefix(('a',), ('a', 'b', 'c')) is True

    def test_suffix_not_prefix(self) -> None:
        assert is_prefix(('b', 'c'), ('a', 'b', 'c')) is False

    def test_disjoint(self) -> None:
        assert is_prefix(('x',), ('a', 'b')) is False

    def test_empty_prefix_on_non_empty(self) -> None:
        assert is_prefix((), ('a', 'b')) is True

    def test_empty_prefix_on_empty(self) -> None:
        assert is_prefix((), ()) is True


# ---------------------------------------------------------------------------
# apply_value
# ---------------------------------------------------------------------------


class TestApplyValue:
    def test_new_key_opens_span(self) -> None:
        open_spans: OpenSpanMap = {}
        emitted: list[RawSpan] = []
        apply_value(open_spans, 'cicd', ('app',), 'v1', T0, emitted)

        assert len(emitted) == 0
        assert ('cicd', ('app',)) in open_spans
        assert open_spans[('cicd', ('app',))].value == 'v1'
        assert open_spans[('cicd', ('app',))].span_start == T0

    def test_same_value_is_noop(self) -> None:
        open_spans: OpenSpanMap = {
            ('cicd', ('app',)): OpenSpan(value='v1', span_start=T0),
        }
        emitted: list[RawSpan] = []
        apply_value(open_spans, 'cicd', ('app',), 'v1', T1, emitted)

        assert len(emitted) == 0
        assert open_spans[('cicd', ('app',))].value == 'v1'
        assert open_spans[('cicd', ('app',))].span_start == T0

    def test_different_value_closes_old_and_opens_new(self) -> None:
        open_spans: OpenSpanMap = {
            ('cicd', ('app',)): OpenSpan(value='v1', span_start=T0),
        }
        emitted: list[RawSpan] = []
        apply_value(open_spans, 'cicd', ('app',), 'v2', T1, emitted)

        assert len(emitted) == 1
        closed_span = emitted[0]
        assert closed_span.source == 'cicd'
        assert closed_span.path == ['app']
        assert closed_span.value == 'v1'
        assert closed_span.start == T0
        assert closed_span.end == T1
        assert closed_span.end_reason == 'value_change'

        assert open_spans[('cicd', ('app',))].value == 'v2'
        assert open_spans[('cicd', ('app',))].span_start == T1


# ---------------------------------------------------------------------------
# close_cascade
# ---------------------------------------------------------------------------


class TestCloseCascade:
    def test_closes_exact_match(self) -> None:
        open_spans: OpenSpanMap = {
            ('cicd', ('app',)): OpenSpan(value='v1', span_start=T0),
        }
        emitted: list[RawSpan] = []
        close_cascade(open_spans, 'cicd', ('app',), T1, emitted)

        assert len(emitted) == 1
        assert emitted[0].path == ['app']
        assert emitted[0].end == T1
        assert emitted[0].end_reason == 'closed'
        assert ('cicd', ('app',)) not in open_spans

    def test_closes_descendants_of_same_source(self) -> None:
        open_spans: OpenSpanMap = {
            ('cicd', ('app',)): OpenSpan(value='v1', span_start=T0),
            ('cicd', ('app', 'plugin')): OpenSpan(value='p1', span_start=T0),
            ('cicd', ('app', 'plugin', 'alpha')): OpenSpan(value='a1', span_start=T0),
        }
        emitted: list[RawSpan] = []
        close_cascade(open_spans, 'cicd', ('app',), T1, emitted)

        assert len(emitted) == 3
        assert len(open_spans) == 0
        for span in emitted:
            assert span.end_reason == 'closed'
            assert span.end == T1

    def test_does_not_touch_other_sources(self) -> None:
        open_spans: OpenSpanMap = {
            ('cicd', ('app',)): OpenSpan(value='v1', span_start=T0),
            ('deploy', ('app',)): OpenSpan(value='d1', span_start=T0),
        }
        emitted: list[RawSpan] = []
        close_cascade(open_spans, 'cicd', ('app',), T1, emitted)

        assert len(emitted) == 1
        assert emitted[0].source == 'cicd'
        assert ('deploy', ('app',)) in open_spans

    def test_noop_when_no_open_span(self) -> None:
        open_spans: OpenSpanMap = {}
        emitted: list[RawSpan] = []
        close_cascade(open_spans, 'cicd', ('nonexistent',), T1, emitted)

        assert len(emitted) == 0
        assert len(open_spans) == 0


# ---------------------------------------------------------------------------
# apply_snapshot
# ---------------------------------------------------------------------------


class TestApplySnapshot:
    def test_closures_before_values_ordering(self) -> None:
        """Open 'foo' at T0, snapshot at T1 closes 'foo' then re-opens with new value."""
        open_spans: OpenSpanMap = {
            ('cicd', ('foo',)): OpenSpan(value='old', span_start=T0),
        }
        emitted: list[RawSpan] = []
        snapshot = SnapshotWithEntries(
            source='cicd',
            observed_at=T1,
            values=[(['foo'], 'new')],
            closures=[['foo']],
        )
        apply_snapshot(open_spans, snapshot, emitted)

        assert len(emitted) == 1
        assert emitted[0].value == 'old'
        assert emitted[0].start == T0
        assert emitted[0].end == T1
        assert emitted[0].end_reason == 'closed'

        assert ('cicd', ('foo',)) in open_spans
        assert open_spans[('cicd', ('foo',))].value == 'new'
        assert open_spans[('cicd', ('foo',))].span_start == T1

    def test_values_only_snapshot(self) -> None:
        open_spans: OpenSpanMap = {}
        emitted: list[RawSpan] = []
        snapshot = SnapshotWithEntries(
            source='cicd',
            observed_at=T0,
            values=[(['app'], 'v1'), (['svc'], 'v2')],
            closures=[],
        )
        apply_snapshot(open_spans, snapshot, emitted)

        assert len(emitted) == 0
        assert len(open_spans) == 2

    def test_closures_only_snapshot(self) -> None:
        open_spans: OpenSpanMap = {
            ('cicd', ('app',)): OpenSpan(value='v1', span_start=T0),
        }
        emitted: list[RawSpan] = []
        snapshot = SnapshotWithEntries(
            source='cicd',
            observed_at=T1,
            values=[],
            closures=[['app']],
        )
        apply_snapshot(open_spans, snapshot, emitted)

        assert len(emitted) == 1
        assert emitted[0].end_reason == 'closed'
        assert len(open_spans) == 0


# ---------------------------------------------------------------------------
# finalize_open_spans
# ---------------------------------------------------------------------------


class TestFinalizeOpenSpans:
    def test_converts_remaining_to_open_ended_spans(self) -> None:
        open_spans: OpenSpanMap = {
            ('cicd', ('app',)): OpenSpan(value='v1', span_start=T0),
            ('deploy', ('svc',)): OpenSpan(value='d1', span_start=T1),
        }
        emitted: list[RawSpan] = []
        finalize_open_spans(open_spans, emitted)

        assert len(emitted) == 2
        for span in emitted:
            assert span.end is None
            assert span.end_reason == 'open'

    def test_empty_map_produces_nothing(self) -> None:
        open_spans: OpenSpanMap = {}
        emitted: list[RawSpan] = []
        finalize_open_spans(open_spans, emitted)

        assert len(emitted) == 0


# ---------------------------------------------------------------------------
# derive_raw_spans (end-to-end)
# ---------------------------------------------------------------------------


class TestDeriveRawSpans:
    def test_single_value_snapshot(self) -> None:
        snapshots = [
            SnapshotWithEntries(
                source='cicd',
                observed_at=T0,
                values=[(['app'], 'v1')],
                closures=[],
            ),
        ]
        spans = derive_raw_spans(snapshots)

        assert len(spans) == 1
        assert spans[0].source == 'cicd'
        assert spans[0].path == ['app']
        assert spans[0].value == 'v1'
        assert spans[0].start == T0
        assert spans[0].end is None
        assert spans[0].end_reason == 'open'

    def test_value_then_value_change(self) -> None:
        snapshots = [
            SnapshotWithEntries(
                source='cicd',
                observed_at=T0,
                values=[(['app'], 'v1')],
                closures=[],
            ),
            SnapshotWithEntries(
                source='cicd',
                observed_at=T1,
                values=[(['app'], 'v2')],
                closures=[],
            ),
        ]
        spans = derive_raw_spans(snapshots)

        assert len(spans) == 2
        closed_span = spans[0]
        assert closed_span.value == 'v1'
        assert closed_span.start == T0
        assert closed_span.end == T1
        assert closed_span.end_reason == 'value_change'

        open_span = spans[1]
        assert open_span.value == 'v2'
        assert open_span.start == T1
        assert open_span.end is None
        assert open_span.end_reason == 'open'

    def test_daily_heartbeat_collapses(self) -> None:
        """30 identical snapshots should collapse into exactly one open-ended span (scenario 9)."""
        snapshots = [
            SnapshotWithEntries(
                source='cicd',
                observed_at=T0 + timedelta(days=day),
                values=[(['app'], 'v1')],
                closures=[],
            )
            for day in range(30)
        ]
        spans = derive_raw_spans(snapshots)

        assert len(spans) == 1
        assert spans[0].value == 'v1'
        assert spans[0].start == T0
        assert spans[0].end is None
        assert spans[0].end_reason == 'open'

    def test_cascading_close(self) -> None:
        """Open app + app/plug + app/plug/alpha, then close app -> three closed spans (scenario 19)."""
        snapshots = [
            SnapshotWithEntries(
                source='cicd',
                observed_at=T0,
                values=[
                    (['app'], 'v1'),
                    (['app', 'plug'], 'p1'),
                    (['app', 'plug', 'alpha'], 'a1'),
                ],
                closures=[],
            ),
            SnapshotWithEntries(
                source='cicd',
                observed_at=T1,
                values=[],
                closures=[['app']],
            ),
        ]
        spans = derive_raw_spans(snapshots)

        assert len(spans) == 3
        for span in spans:
            assert span.end == T1
            assert span.end_reason == 'closed'
            assert span.start == T0

        paths = [tuple(span.path) for span in spans]
        assert ('app',) in paths
        assert ('app', 'plug') in paths
        assert ('app', 'plug', 'alpha') in paths
