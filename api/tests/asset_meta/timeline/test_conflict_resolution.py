"""Unit tests for multi-source conflict resolution."""

import logging
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from tropek.modules.asset_meta.timeline.conflict_resolution import (
    compute_latest_observation_per_source,
    group_spans_by_path,
    log_source_conflict,
    pick_winning_source,
    resolve_multi_source_conflicts,
)
from tropek.modules.asset_meta.timeline.types import RawSpan

T0 = datetime(2026, 4, 16, 10, 0, 0, tzinfo=UTC)
T1 = T0 + timedelta(hours=1)
T2 = T0 + timedelta(hours=2)
ASSET_ID = uuid.uuid4()


def make_span(
    source: str = 'cicd',
    path: list[str] | None = None,
    value: str = '1.0',
    start: datetime = T0,
    end: datetime | None = T1,
    end_reason: str = 'value_change',
) -> RawSpan:
    return RawSpan(
        source=source,
        path=path or ['app'],
        value=value,
        start=start,
        end=end,
        end_reason=end_reason,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# group_spans_by_path
# ---------------------------------------------------------------------------


class TestGroupSpansByPath:
    def test_empty_input_returns_empty_dict(self) -> None:
        result = group_spans_by_path([])
        assert result == {}

    def test_single_path_input_produces_one_key(self) -> None:
        span = make_span(path=['app'])
        result = group_spans_by_path([span])
        assert list(result.keys()) == [('app',)]
        assert result[('app',)] == [span]

    def test_multi_path_input_with_duplicates_within_path(self) -> None:
        span_app_1 = make_span(source='cicd', path=['app'], value='1.0')
        span_app_2 = make_span(source='deploy', path=['app'], value='2.0')
        span_svc = make_span(source='cicd', path=['svc'], value='3.0')
        result = group_spans_by_path([span_app_1, span_app_2, span_svc])

        assert set(result.keys()) == {('app',), ('svc',)}
        assert len(result[('app',)]) == 2
        assert span_app_1 in result[('app',)]
        assert span_app_2 in result[('app',)]
        assert result[('svc',)] == [span_svc]


# ---------------------------------------------------------------------------
# compute_latest_observation_per_source
# ---------------------------------------------------------------------------


class TestComputeLatestObservationPerSource:
    def test_two_sources_winner_based_on_latest_end(self) -> None:
        span_cicd = make_span(source='cicd', end=T1)
        span_deploy = make_span(source='deploy', end=T2)
        result = compute_latest_observation_per_source([span_cicd, span_deploy])

        assert result['cicd'] == T1
        assert result['deploy'] == T2

    def test_open_span_beats_closed_past_span(self) -> None:
        span_closed = make_span(source='cicd', end=T2)
        span_open = make_span(source='deploy', end=None, end_reason='open')
        result = compute_latest_observation_per_source([span_closed, span_open])

        # open span gets the sentinel (datetime.max with utc), which is far in the future
        assert result['deploy'] > result['cicd']

    def test_multiple_spans_same_source_takes_latest(self) -> None:
        span_early = make_span(source='cicd', end=T0)
        span_late = make_span(source='cicd', end=T2)
        result = compute_latest_observation_per_source([span_early, span_late])

        assert result['cicd'] == T2
        assert len(result) == 1


# ---------------------------------------------------------------------------
# pick_winning_source
# ---------------------------------------------------------------------------


class TestPickWinningSource:
    def test_unambiguous_winner(self) -> None:
        sources_latest = {'cicd': T1, 'deploy': T2}
        assert pick_winning_source(sources_latest) == 'deploy'

    def test_tie_on_timestamp_alphabetical_source_wins(self) -> None:
        # 'zebra' vs 'apple' — alphabetically 'zebra' > 'apple', so 'zebra' wins
        sources_latest = {'apple': T1, 'zebra': T1}
        assert pick_winning_source(sources_latest) == 'zebra'

    def test_single_source_returns_itself(self) -> None:
        sources_latest = {'only_source': T0}
        assert pick_winning_source(sources_latest) == 'only_source'


# ---------------------------------------------------------------------------
# log_source_conflict
# ---------------------------------------------------------------------------


class TestLogSourceConflict:
    def test_emits_warning_with_correct_extra_fields(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger('test.conflict_resolution')
        asset_id = uuid.uuid4()
        path = ('app', 'plugin')
        sources_latest = {'cicd': T1, 'deploy': T2}
        winner = 'deploy'

        with caplog.at_level(logging.WARNING, logger='test.conflict_resolution'):
            log_source_conflict(logger, asset_id, path, sources_latest, winner)

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.levelno == logging.WARNING
        assert record.message == 'asset_meta_timeline.multi_source_conflict'
        assert record.asset_id == str(asset_id)  # type: ignore[attr-defined]
        assert record.path == ['app', 'plugin']  # type: ignore[attr-defined]
        assert record.sources == ['cicd', 'deploy']  # type: ignore[attr-defined]
        assert record.winner == winner  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# resolve_multi_source_conflicts
# ---------------------------------------------------------------------------


class TestResolveMultiSourceConflicts:
    def test_single_source_path_passes_through_unchanged(self) -> None:
        logger = logging.getLogger('test.resolve')
        span = make_span(source='cicd', path=['app'])
        result = resolve_multi_source_conflicts([span], ASSET_ID, logger)
        assert result == [span]

    def test_two_source_conflict_drops_loser_emits_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        logger = logging.getLogger('test.resolve_conflict')
        # cicd has older data (T1), deploy has newer (T2) — deploy wins
        span_cicd = make_span(source='cicd', path=['app'], end=T1)
        span_deploy = make_span(source='deploy', path=['app'], end=T2)

        with caplog.at_level(logging.WARNING, logger='test.resolve_conflict'):
            result = resolve_multi_source_conflicts(
                [span_cicd, span_deploy], ASSET_ID, logger
            )

        assert result == [span_deploy]
        assert len(caplog.records) == 1
        assert caplog.records[0].message == 'asset_meta_timeline.multi_source_conflict'

    def test_three_sources_same_path_picks_correct_winner(self) -> None:
        logger = logging.getLogger('test.resolve_three')
        span_old = make_span(source='cicd', path=['app'], end=T0)
        span_mid = make_span(source='deploy', path=['app'], end=T1)
        # 'monitoring' has an open span → sentinel beats any closed end
        span_open = make_span(source='monitoring', path=['app'], end=None, end_reason='open')

        result = resolve_multi_source_conflicts(
            [span_old, span_mid, span_open], ASSET_ID, logger
        )

        assert len(result) == 1
        assert result[0].source == 'monitoring'
