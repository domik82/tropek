"""Tests for timeline composition."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from tests.conftest import validate_profile_schema


class TestDurationParsing:
    def test_parse_seconds(self):
        from slo_generator.composer import parse_duration

        assert parse_duration("30s") == timedelta(seconds=30)

    def test_parse_minutes(self):
        from slo_generator.composer import parse_duration

        assert parse_duration("5m") == timedelta(minutes=5)

    def test_parse_hours(self):
        from slo_generator.composer import parse_duration

        assert parse_duration("720h") == timedelta(hours=720)

    def test_parse_days(self):
        from slo_generator.composer import parse_duration

        assert parse_duration("30d") == timedelta(days=30)

    def test_invalid_duration_raises(self):
        from slo_generator.composer import parse_duration

        with pytest.raises(ValueError, match="invalid duration"):
            parse_duration("abc")


class TestTimelineConfig:
    def test_from_yaml_minimal(self, tmp_path: Path):
        from slo_generator.composer import TimelineComposer

        yaml_content = """
timeline:
  start: "2026-03-01T00:00:00Z"
  duration: 168h
  events: []
"""
        yaml_path = tmp_path / "test.yaml"
        yaml_path.write_text(yaml_content)

        composer = TimelineComposer.from_yaml(yaml_path)
        assert composer.config.start == datetime(2026, 3, 1, tzinfo=UTC)
        assert composer.config.end == datetime(2026, 3, 8, tzinfo=UTC)
        assert composer.config.resolution_seconds == 30  # default
        assert composer.config.baseline == "healthy"  # default
        assert len(composer.config.events) == 0

    def test_from_yaml_with_end_instead_of_duration(self, tmp_path: Path):
        from slo_generator.composer import TimelineComposer

        yaml_content = """
timeline:
  start: "2026-03-01T00:00:00Z"
  end: "2026-03-08T00:00:00Z"
  events: []
"""
        yaml_path = tmp_path / "test.yaml"
        yaml_path.write_text(yaml_content)

        composer = TimelineComposer.from_yaml(yaml_path)
        assert composer.config.end == datetime(2026, 3, 8, tzinfo=UTC)

    def test_from_yaml_with_events(self, tmp_path: Path):
        from slo_generator.composer import TimelineComposer

        yaml_content = """
timeline:
  start: "2026-03-01T00:00:00Z"
  duration: 168h
  resolution: 10s
  events:
    - type: outage
      at: 100h
      duration: 30m
      restart_gap: 1m
      resolution: 1s
      params:
        recovery_minutes: 5
"""
        yaml_path = tmp_path / "test.yaml"
        yaml_path.write_text(yaml_content)

        composer = TimelineComposer.from_yaml(yaml_path)
        assert composer.config.resolution_seconds == 10
        assert len(composer.config.events) == 1

        event = composer.config.events[0]
        assert event.type == "outage"
        assert event.at == timedelta(hours=100)
        assert event.duration == timedelta(minutes=30)
        assert event.restart_gap == timedelta(minutes=1)
        assert event.resolution == 1
        assert event.params == {"recovery_minutes": 5}

    def test_validates_overlapping_events(self, tmp_path: Path):
        from slo_generator.composer import TimelineComposer

        yaml_content = """
timeline:
  start: "2026-03-01T00:00:00Z"
  duration: 168h
  events:
    - type: outage
      at: 100h
      duration: 5h
    - type: degradation
      at: 103h
      duration: 5h
"""
        yaml_path = tmp_path / "test.yaml"
        yaml_path.write_text(yaml_content)

        with pytest.raises(ValueError, match="overlap"):
            TimelineComposer.from_yaml(yaml_path)

    def test_validates_event_exceeds_timeline(self, tmp_path: Path):
        from slo_generator.composer import TimelineComposer

        yaml_content = """
timeline:
  start: "2026-03-01T00:00:00Z"
  duration: 24h
  events:
    - type: outage
      at: 23h
      duration: 3h
"""
        yaml_path = tmp_path / "test.yaml"
        yaml_path.write_text(yaml_content)

        with pytest.raises(ValueError, match="exceeds"):
            TimelineComposer.from_yaml(yaml_path)

    def test_validates_event_resolution_coarser_than_global(self, tmp_path: Path):
        from slo_generator.composer import TimelineComposer

        yaml_content = """
timeline:
  start: "2026-03-01T00:00:00Z"
  duration: 24h
  resolution: 30s
  events:
    - type: outage
      at: 12h
      duration: 1h
      resolution: 60s
"""
        yaml_path = tmp_path / "test.yaml"
        yaml_path.write_text(yaml_content)

        with pytest.raises(ValueError, match="coarser"):
            TimelineComposer.from_yaml(yaml_path)


class TestTimelineComposition:
    def test_pure_baseline_generates_healthy_data(self, tmp_path: Path):
        from slo_generator.composer import TimelineComposer

        yaml_content = """
timeline:
  start: "2026-03-20T00:00:00Z"
  duration: 2h
  resolution: 30s
  events: []
"""
        yaml_path = tmp_path / "test.yaml"
        yaml_path.write_text(yaml_content)

        composer = TimelineComposer.from_yaml(yaml_path)
        chunks = list(composer.generate())

        assert len(chunks) == 2  # 2 hours = 2 chunks
        df = pd.concat(chunks)
        validate_profile_schema(df)
        assert (df["error_rate"] < 0.01).all()  # healthy

    def test_event_replaces_baseline_window(self, tmp_path: Path):
        from slo_generator.composer import TimelineComposer

        yaml_content = """
timeline:
  start: "2026-03-20T00:00:00Z"
  duration: 4h
  resolution: 30s
  events:
    - type: outage
      at: 1h
      duration: 30m
"""
        yaml_path = tmp_path / "test.yaml"
        yaml_path.write_text(yaml_content)

        composer = TimelineComposer.from_yaml(yaml_path)
        chunks = list(composer.generate())
        df = pd.concat(chunks)

        validate_profile_schema(df)

        api = df[(df["service"] == "api") & (df["host"] == "host1")]
        start = datetime(2026, 3, 20, tzinfo=UTC)

        # During outage window, error rate should be elevated
        outage_window = api[
            (api["timestamp"] >= start + timedelta(hours=1, minutes=5))
            & (api["timestamp"] < start + timedelta(hours=1, minutes=20))
        ]
        assert outage_window["error_rate"].mean() > 0.3

        # Before outage, should be healthy
        before = api[api["timestamp"] < start + timedelta(hours=1)]
        assert before["error_rate"].mean() < 0.01

    def test_restart_gap_creates_missing_data(self, tmp_path: Path):
        from slo_generator.composer import TimelineComposer

        yaml_content = """
timeline:
  start: "2026-03-20T00:00:00Z"
  duration: 2h
  resolution: 30s
  events:
    - type: outage
      at: 30m
      duration: 20m
      restart_gap: 5m
"""
        yaml_path = tmp_path / "test.yaml"
        yaml_path.write_text(yaml_content)

        composer = TimelineComposer.from_yaml(yaml_path)
        chunks = list(composer.generate())
        df = pd.concat(chunks)

        api = df[(df["service"] == "api") & (df["host"] == "host1")]
        start = datetime(2026, 3, 20, tzinfo=UTC)

        # There should be no data in the gap window (50min to 55min)
        gap_data = api[
            (api["timestamp"] >= start + timedelta(minutes=50))
            & (api["timestamp"] < start + timedelta(minutes=55))
        ]
        assert len(gap_data) == 0

    def test_event_resolution_override(self, tmp_path: Path):
        from slo_generator.composer import TimelineComposer

        yaml_content = """
timeline:
  start: "2026-03-20T00:00:00Z"
  duration: 2h
  resolution: 30s
  events:
    - type: step_change
      at: 30m
      duration: 30m
      resolution: 5s
"""
        yaml_path = tmp_path / "test.yaml"
        yaml_path.write_text(yaml_content)

        composer = TimelineComposer.from_yaml(yaml_path)
        chunks = list(composer.generate())
        df = pd.concat(chunks)

        api = df[(df["service"] == "api") & (df["host"] == "host1")]
        start = datetime(2026, 3, 20, tzinfo=UTC)

        # Event window should have finer resolution (5s = more data points)
        event_data = api[
            (api["timestamp"] >= start + timedelta(minutes=30))
            & (api["timestamp"] < start + timedelta(hours=1))
        ]
        baseline_data = api[api["timestamp"] < start + timedelta(minutes=30)]

        # More data points per minute in event window
        event_per_min = len(event_data) / 30
        baseline_per_min = len(baseline_data) / 30
        assert event_per_min > baseline_per_min * 3  # 5s vs 30s = 6x
