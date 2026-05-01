"""Unit tests for asset meta timeline window clipping (§7.3)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from tropek.modules.asset_meta.timeline.clipping import clip_one_span, clip_spans, compute_span_classes
from tropek.modules.asset_meta.timeline.types import ClippedSpan, RawSpan

WINDOW_FROM = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC)
WINDOW_TO = datetime(2026, 4, 30, 0, 0, 0, tzinfo=UTC)


def make_span(
    start: datetime = WINDOW_FROM,
    end: datetime | None = WINDOW_TO,
    end_reason: str = 'value_change',
    **kwargs: object,
) -> RawSpan:
    return RawSpan(
        source='cicd',
        path=['app'],
        value='1.0',
        start=start,
        end=end,
        end_reason=end_reason,  # type: ignore[arg-type]
        **kwargs,
    )


# ---------------------------------------------------------------------------
# compute_span_classes — exhaustive 2x3x2 = 12 parametrized cases
# ---------------------------------------------------------------------------

# Each case is a tuple of:
#   (clipped_left, end_state, end_reason, expected_classes)
# clipped_left: True  → clipped_start > span.start
# end_state: 'none' | 'beyond' | 'within'
# end_reason: 'closed' | 'value_change'

_ONE_HOUR = timedelta(hours=1)

_COMPUTE_CLASSES_CASES = [
    # --- not clipped left, end=None, not closed ---
    pytest.param(
        False, 'none', 'value_change',
        ['meta-span', 'meta-span-open'],
        id='not_left__open__not_closed',
    ),
    # --- not clipped left, end=None, closed (unusual but logically possible) ---
    pytest.param(
        False, 'none', 'closed',
        ['meta-span', 'meta-span-open', 'meta-span-closed'],
        id='not_left__open__closed',
    ),
    # --- not clipped left, end beyond window, not closed ---
    pytest.param(
        False, 'beyond', 'value_change',
        ['meta-span', 'meta-span-clipped-right'],
        id='not_left__beyond__not_closed',
    ),
    # --- not clipped left, end beyond window, closed ---
    pytest.param(
        False, 'beyond', 'closed',
        ['meta-span', 'meta-span-clipped-right', 'meta-span-closed'],
        id='not_left__beyond__closed',
    ),
    # --- not clipped left, end within window, not closed ---
    pytest.param(
        False, 'within', 'value_change',
        ['meta-span'],
        id='not_left__within__not_closed',
    ),
    # --- not clipped left, end within window, closed ---
    pytest.param(
        False, 'within', 'closed',
        ['meta-span', 'meta-span-closed'],
        id='not_left__within__closed',
    ),
    # --- clipped left, end=None, not closed ---
    pytest.param(
        True, 'none', 'value_change',
        ['meta-span', 'meta-span-clipped-left', 'meta-span-open'],
        id='clipped_left__open__not_closed',
    ),
    # --- clipped left, end=None, closed ---
    pytest.param(
        True, 'none', 'closed',
        ['meta-span', 'meta-span-clipped-left', 'meta-span-open', 'meta-span-closed'],
        id='clipped_left__open__closed',
    ),
    # --- clipped left, end beyond window, not closed ---
    pytest.param(
        True, 'beyond', 'value_change',
        ['meta-span', 'meta-span-clipped-left', 'meta-span-clipped-right'],
        id='clipped_left__beyond__not_closed',
    ),
    # --- clipped left, end beyond window, closed ---
    pytest.param(
        True, 'beyond', 'closed',
        ['meta-span', 'meta-span-clipped-left', 'meta-span-clipped-right', 'meta-span-closed'],
        id='clipped_left__beyond__closed',
    ),
    # --- clipped left, end within window, not closed ---
    pytest.param(
        True, 'within', 'value_change',
        ['meta-span', 'meta-span-clipped-left'],
        id='clipped_left__within__not_closed',
    ),
    # --- clipped left, end within window, closed ---
    pytest.param(
        True, 'within', 'closed',
        ['meta-span', 'meta-span-clipped-left', 'meta-span-closed'],
        id='clipped_left__within__closed',
    ),
]


@pytest.mark.parametrize(
    ('clipped_left', 'end_state', 'end_reason', 'expected_classes'),
    _COMPUTE_CLASSES_CASES,
)
def test_compute_span_classes(
    clipped_left: bool,
    end_state: str,
    end_reason: str,
    expected_classes: list[str],
) -> None:
    # Build span.start and clipped_start based on clipped_left flag
    if clipped_left:
        span_start = WINDOW_FROM - _ONE_HOUR
        clipped_start = WINDOW_FROM
    else:
        span_start = WINDOW_FROM
        clipped_start = WINDOW_FROM

    # Build span.end based on end_state
    if end_state == 'none':
        span_end = None
    elif end_state == 'beyond':
        span_end = WINDOW_TO + _ONE_HOUR
    else:  # within
        span_end = WINDOW_TO - _ONE_HOUR

    span = make_span(start=span_start, end=span_end, end_reason=end_reason)
    result = compute_span_classes(
        span=span,
        window_from=WINDOW_FROM,
        window_to=WINDOW_TO,
        clipped_start=clipped_start,
    )
    assert result == expected_classes


# ---------------------------------------------------------------------------
# clip_one_span — boundary cases
# ---------------------------------------------------------------------------


class TestClipOneSpan:
    def test_span_entirely_before_window_returns_none(self) -> None:
        span = make_span(
            start=WINDOW_FROM - timedelta(days=10),
            end=WINDOW_FROM - timedelta(days=1),
        )
        assert clip_one_span(span, WINDOW_FROM, WINDOW_TO) is None

    def test_span_entirely_after_window_returns_none(self) -> None:
        span = make_span(
            start=WINDOW_TO + timedelta(days=1),
            end=WINDOW_TO + timedelta(days=10),
        )
        assert clip_one_span(span, WINDOW_FROM, WINDOW_TO) is None

    def test_span_end_exactly_at_window_from_returns_none(self) -> None:
        # effective_end == window_from → entirely before
        span = make_span(
            start=WINDOW_FROM - timedelta(days=2),
            end=WINDOW_FROM,
        )
        assert clip_one_span(span, WINDOW_FROM, WINDOW_TO) is None

    def test_span_start_exactly_at_window_to_returns_none(self) -> None:
        # span.start == window_to → entirely after
        span = make_span(
            start=WINDOW_TO,
            end=WINDOW_TO + timedelta(days=1),
        )
        assert clip_one_span(span, WINDOW_FROM, WINDOW_TO) is None

    def test_zero_length_span_inside_window(self) -> None:
        midpoint = WINDOW_FROM + (WINDOW_TO - WINDOW_FROM) / 2
        span = make_span(start=midpoint, end=midpoint)
        result = clip_one_span(span, WINDOW_FROM, WINDOW_TO)
        assert result is not None
        assert result.start == midpoint
        assert result.end == midpoint
        assert 'meta-span' in result.className

    def test_open_span_is_clipped_to_window_to_with_open_class(self) -> None:
        span = make_span(
            start=WINDOW_FROM + timedelta(days=5),
            end=None,
            end_reason='open',
        )
        result = clip_one_span(span, WINDOW_FROM, WINDOW_TO)
        assert result is not None
        assert result.end == WINDOW_TO
        assert 'meta-span-open' in result.className

    def test_span_overlapping_left_is_clipped_and_has_clipped_left_class(self) -> None:
        span = make_span(
            start=WINDOW_FROM - timedelta(days=5),
            end=WINDOW_FROM + timedelta(days=5),
        )
        result = clip_one_span(span, WINDOW_FROM, WINDOW_TO)
        assert result is not None
        assert result.start == WINDOW_FROM
        assert 'meta-span-clipped-left' in result.className

    def test_span_overlapping_right_is_clipped_and_has_clipped_right_class(self) -> None:
        span = make_span(
            start=WINDOW_TO - timedelta(days=5),
            end=WINDOW_TO + timedelta(days=5),
        )
        result = clip_one_span(span, WINDOW_FROM, WINDOW_TO)
        assert result is not None
        assert result.end == WINDOW_TO
        assert 'meta-span-clipped-right' in result.className

    def test_span_fully_inside_window_is_unchanged(self) -> None:
        inner_start = WINDOW_FROM + timedelta(days=5)
        inner_end = WINDOW_TO - timedelta(days=5)
        span = make_span(start=inner_start, end=inner_end)
        result = clip_one_span(span, WINDOW_FROM, WINDOW_TO)
        assert result is not None
        assert result.start == inner_start
        assert result.end == inner_end
        assert result.className == 'meta-span'

    def test_closed_span_carries_closed_class(self) -> None:
        span = make_span(
            start=WINDOW_FROM + timedelta(days=1),
            end=WINDOW_FROM + timedelta(days=3),
            end_reason='closed',
        )
        result = clip_one_span(span, WINDOW_FROM, WINDOW_TO)
        assert result is not None
        assert 'meta-span-closed' in result.className

    def test_returned_clipped_span_is_a_clipped_span_instance(self) -> None:
        span = make_span()
        result = clip_one_span(span, WINDOW_FROM, WINDOW_TO)
        assert isinstance(result, ClippedSpan)

    def test_source_path_value_are_preserved(self) -> None:
        span = RawSpan(
            source='deploy',
            path=['svc', 'plugin'],
            value='2.5',
            start=WINDOW_FROM + timedelta(days=1),
            end=WINDOW_TO - timedelta(days=1),
            end_reason='value_change',
        )
        result = clip_one_span(span, WINDOW_FROM, WINDOW_TO)
        assert result is not None
        assert result.source == 'deploy'
        assert result.path == ['svc', 'plugin']
        assert result.value == '2.5'


# ---------------------------------------------------------------------------
# clip_spans — mix of in-window, before-window, after-window spans
# ---------------------------------------------------------------------------


class TestClipSpans:
    def test_empty_input_returns_empty_list(self) -> None:
        assert clip_spans([], WINDOW_FROM, WINDOW_TO) == []

    def test_all_spans_outside_window_returns_empty(self) -> None:
        before = make_span(
            start=WINDOW_FROM - timedelta(days=10),
            end=WINDOW_FROM - timedelta(days=1),
        )
        after = make_span(
            start=WINDOW_TO + timedelta(days=1),
            end=WINDOW_TO + timedelta(days=5),
        )
        assert clip_spans([before, after], WINDOW_FROM, WINDOW_TO) == []

    def test_mix_keeps_only_in_window_spans(self) -> None:
        before = make_span(
            start=WINDOW_FROM - timedelta(days=10),
            end=WINDOW_FROM - timedelta(days=1),
        )
        inside = make_span(
            start=WINDOW_FROM + timedelta(days=5),
            end=WINDOW_TO - timedelta(days=5),
        )
        after = make_span(
            start=WINDOW_TO + timedelta(days=1),
            end=WINDOW_TO + timedelta(days=5),
        )
        result = clip_spans([before, inside, after], WINDOW_FROM, WINDOW_TO)
        assert len(result) == 1

    def test_mix_result_count_matches_in_window_count(self) -> None:
        spans = [
            make_span(  # before
                start=WINDOW_FROM - timedelta(days=5),
                end=WINDOW_FROM - timedelta(days=1),
            ),
            make_span(  # inside 1
                start=WINDOW_FROM + timedelta(days=1),
                end=WINDOW_FROM + timedelta(days=3),
            ),
            make_span(  # inside 2
                start=WINDOW_FROM + timedelta(days=10),
                end=WINDOW_TO - timedelta(days=5),
            ),
            make_span(  # after
                start=WINDOW_TO + timedelta(days=2),
                end=WINDOW_TO + timedelta(days=10),
            ),
        ]
        result = clip_spans(spans, WINDOW_FROM, WINDOW_TO)
        assert len(result) == 2

    def test_overlapping_span_is_included_and_clipped(self) -> None:
        overlapping_left = make_span(
            start=WINDOW_FROM - timedelta(days=3),
            end=WINDOW_FROM + timedelta(days=3),
        )
        result = clip_spans([overlapping_left], WINDOW_FROM, WINDOW_TO)
        assert len(result) == 1
        assert result[0].start == WINDOW_FROM

    def test_all_spans_inside_window_all_returned(self) -> None:
        spans = [
            make_span(
                start=WINDOW_FROM + timedelta(days=i),
                end=WINDOW_FROM + timedelta(days=i + 1),
            )
            for i in range(5)
        ]
        result = clip_spans(spans, WINDOW_FROM, WINDOW_TO)
        assert len(result) == 5
