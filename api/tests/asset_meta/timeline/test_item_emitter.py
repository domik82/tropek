"""Unit tests for asset_meta timeline item_emitter (§7.5)."""

from __future__ import annotations

from datetime import UTC, datetime

from tropek.modules.asset_meta.timeline.item_emitter import build_items_wire, item_from_span
from tropek.modules.asset_meta.timeline.tree_builder import encode_path_as_group_id
from tropek.modules.asset_meta.timeline.types import ClippedSpan


def make_clipped(path=None, **overrides):
    defaults = {
        'source': 'cicd',
        'label_path': path or ['app'],
        'value': '1.0',
        'start': datetime(2026, 4, 1, tzinfo=UTC),
        'end': datetime(2026, 4, 30, tzinfo=UTC),
        'className': 'meta-span',
    }
    defaults.update(overrides)
    return ClippedSpan(**defaults)


class TestItemFromSpan:
    def test_id_uses_index(self):
        span = make_clipped()
        item = item_from_span(span, index=7)
        assert item['id'] == 's7'

    def test_group_encodes_path(self):
        span = make_clipped(path=['app', 'pkg'])
        item = item_from_span(span, index=0)
        assert item['group'] == encode_path_as_group_id(('app', 'pkg'))

    def test_content_equals_value(self):
        span = make_clipped(value='2.3.1')
        item = item_from_span(span, index=0)
        assert item['content'] == '2.3.1'

    def test_start_is_iso_string(self):
        span = make_clipped(start=datetime(2026, 4, 1, tzinfo=UTC))
        item = item_from_span(span, index=0)
        assert item['start'] == datetime(2026, 4, 1, tzinfo=UTC).isoformat()

    def test_end_is_iso_string(self):
        span = make_clipped(end=datetime(2026, 4, 30, tzinfo=UTC))
        item = item_from_span(span, index=0)
        assert item['end'] == datetime(2026, 4, 30, tzinfo=UTC).isoformat()

    def test_type_is_range(self):
        span = make_clipped()
        item = item_from_span(span, index=0)
        assert item['type'] == 'range'

    def test_class_name_matches_span(self):
        span = make_clipped(className='meta-span')
        item = item_from_span(span, index=0)
        assert item['className'] == 'meta-span'

    def test_source_matches_span(self):
        span = make_clipped(source='cicd')
        item = item_from_span(span, index=0)
        assert item['source'] == 'cicd'


class TestBuildItemsWire:
    def test_length_matches_span_count(self):
        spans = [make_clipped(value=str(i)) for i in range(3)]
        items = build_items_wire(spans)
        assert len(items) == 3

    def test_ids_are_sequential(self):
        spans = [make_clipped(value=str(i)) for i in range(3)]
        items = build_items_wire(spans)
        assert [item['id'] for item in items] == ['s0', 's1', 's2']

    def test_empty_spans_returns_empty_list(self):
        assert build_items_wire([]) == []
