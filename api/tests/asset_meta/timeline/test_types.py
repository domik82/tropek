from datetime import UTC, datetime

from tropek.modules.asset_meta.timeline.types import (
    ClippedSpan,
    OpenSpan,
    OpenSpanMap,
    RawSpan,
    SnapshotWithEntries,
)


def test_raw_span_fields() -> None:
    span = RawSpan(
        source='cicd',
        label_path=['app'],
        value='1.0',
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=None,
        end_reason='open',
    )
    assert span.source == 'cicd'
    assert span.label_path == ['app']
    assert span.value == '1.0'
    assert span.start == datetime(2026, 1, 1, tzinfo=UTC)
    assert span.end is None
    assert span.end_reason == 'open'


def test_clipped_span_fields() -> None:
    span = ClippedSpan(
        source='deploy',
        label_path=['svc', 'env'],
        value='2.0',
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=datetime(2026, 1, 2, tzinfo=UTC),
        className='pass',
    )
    assert span.source == 'deploy'
    assert span.label_path == ['svc', 'env']
    assert span.value == '2.0'
    assert span.start == datetime(2026, 1, 1, tzinfo=UTC)
    assert span.end == datetime(2026, 1, 2, tzinfo=UTC)
    assert span.className == 'pass'


def test_open_span_fields() -> None:
    span = OpenSpan(value='3.0', span_start=datetime(2026, 2, 1, tzinfo=UTC))
    assert span.value == '3.0'
    assert span.span_start == datetime(2026, 2, 1, tzinfo=UTC)


def test_snapshot_with_entries_fields() -> None:
    snapshot = SnapshotWithEntries(
        source='cicd',
        observed_at=datetime(2026, 3, 1, tzinfo=UTC),
        values=[(['app'], 'v1')],
        closures=[['old-key']],
    )
    assert snapshot.source == 'cicd'
    assert snapshot.observed_at == datetime(2026, 3, 1, tzinfo=UTC)
    assert snapshot.values == [(['app'], 'v1')]
    assert snapshot.closures == [['old-key']]


def test_open_span_map_is_dict_type() -> None:
    open_span_map: OpenSpanMap = {
        ('cicd', ('app',)): OpenSpan(value='1.0', span_start=datetime(2026, 1, 1, tzinfo=UTC)),
    }
    assert len(open_span_map) == 1
