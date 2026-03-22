"""Timeline composer — composes continuous timelines from baseline + event splices."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from slo_generator.generator_config import GeneratorConfig
from slo_generator.raw import RawChunk
from slo_generator.scenarios import get_scenario


def parse_duration(s: str) -> timedelta:
    """Parse a duration string like '30s', '5m', '2h', '30d' into a timedelta."""
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([smhd])", s.strip())
    if not match:
        raise ValueError(
            f"invalid duration string: {s!r}, expected format like '30s', '5m', '2h', '30d'"
        )
    value = float(match.group(1))
    unit = match.group(2)
    units = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}
    return timedelta(**{units[unit]: value})


def _parse_resolution_seconds(s: str) -> int:
    """Parse a duration string and return total seconds as int."""
    td = parse_duration(s)
    return int(td.total_seconds())


def _parse_datetime(s: str) -> datetime:
    """Parse an ISO 8601 datetime string to a timezone-aware datetime."""
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


@dataclass
class EventSpec:
    """Specification for a single event in a timeline."""

    type: str
    at: timedelta
    duration: timedelta
    restart_gap: timedelta = field(default_factory=timedelta)
    resolution: int | None = None
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class TimelineConfig:
    """Parsed and validated timeline configuration."""

    start: datetime
    end: datetime
    resolution_seconds: int
    baseline: str
    events: list[EventSpec]


class TimelineComposer:
    """Composes a continuous timeline from a healthy baseline + event splices."""

    def __init__(self, config: TimelineConfig, generator_config: GeneratorConfig | None = None):
        self.config = config
        self.generator_config = generator_config or GeneratorConfig.default()

    @classmethod
    def from_yaml(
        cls,
        path: Path,
        generator_config: GeneratorConfig | None = None,
    ) -> TimelineComposer:
        """Load and validate a timeline from a YAML file."""
        with open(path) as f:
            raw = yaml.safe_load(f)

        tl = raw["timeline"]
        start = _parse_datetime(tl["start"])

        if "duration" in tl:
            end = start + parse_duration(tl["duration"])
        elif "end" in tl:
            end = _parse_datetime(tl["end"])
        else:
            raise ValueError("timeline must have either 'duration' or 'end'")

        resolution_seconds = _parse_resolution_seconds(tl.get("resolution", "30s"))
        baseline = tl.get("baseline", "healthy")

        events = []
        for raw_event in tl.get("events", []):
            event = EventSpec(
                type=raw_event["type"],
                at=parse_duration(str(raw_event["at"])),
                duration=parse_duration(str(raw_event["duration"])),
                restart_gap=parse_duration(str(raw_event.get("restart_gap", "0s"))),
                resolution=(
                    _parse_resolution_seconds(str(raw_event["resolution"]))
                    if "resolution" in raw_event
                    else None
                ),
                params=raw_event.get("params", {}),
            )
            events.append(event)

        config = TimelineConfig(
            start=start,
            end=end,
            resolution_seconds=resolution_seconds,
            baseline=baseline,
            events=events,
        )

        _validate_config(config)
        return cls(config, generator_config=generator_config)

    def generate(
        self,
        resolution_seconds: int = 30,
        chunk_hours: int = 1,
    ) -> Iterator[RawChunk]:
        """Yield composed RawChunk lists."""
        baseline = get_scenario(
            self.config.baseline,
            start=self.config.start,
            end=self.config.end,
            config=self.generator_config,
        )

        event_scenarios = []
        for event in sorted(self.config.events, key=lambda e: e.at):
            event_start = self.config.start + event.at
            event_end = event_start + event.duration
            scenario = get_scenario(
                event.type,
                start=event_start,
                end=event_end,
                config=self.generator_config,
                event_mode=True,
                **event.params,
            )
            event_scenarios.append((event, scenario, event_start, event_end))

        chunk_start = self.config.start
        chunk_delta = timedelta(hours=chunk_hours)

        while chunk_start < self.config.end:
            chunk_end = min(chunk_start + chunk_delta, self.config.end)

            overlapping = [
                (ev, sc, es, ee)
                for ev, sc, es, ee in event_scenarios
                if es < chunk_end and ee > chunk_start
            ]

            chunk = baseline.generate_window(chunk_start, chunk_end, self.config.resolution_seconds)

            if overlapping:
                chunk = self._splice_events(chunk, chunk_start, chunk_end, overlapping)

            if chunk:
                yield chunk

            chunk_start = chunk_end

    def _splice_events(
        self,
        chunk: RawChunk,
        chunk_start: datetime,
        chunk_end: datetime,
        overlapping: list[tuple],
    ) -> RawChunk:
        """Replace baseline samples with event data and apply restart gaps."""
        for event, scenario, ev_start, ev_end in overlapping:
            overlap_start = max(chunk_start, ev_start)
            overlap_end = min(chunk_end, ev_end)
            ev_resolution = event.resolution or self.config.resolution_seconds

            event_data = scenario.generate_window(overlap_start, overlap_end, ev_resolution)

            # Remove baseline samples in the event window
            chunk = [s for s in chunk if s.timestamp < overlap_start or s.timestamp >= overlap_end]
            chunk.extend(event_data)

            # Apply restart gap (remove samples during gap)
            if event.restart_gap.total_seconds() > 0:
                gap_end = overlap_end + event.restart_gap
                chunk = [s for s in chunk if s.timestamp < overlap_end or s.timestamp >= gap_end]

        return sorted(chunk, key=lambda s: s.timestamp)


def _validate_config(config: TimelineConfig) -> None:
    """Validate timeline configuration rules."""
    total_duration = config.end - config.start

    sorted_events = sorted(config.events, key=lambda e: e.at)

    for event in sorted_events:
        if event.at + event.duration > total_duration:
            raise ValueError(
                f"event {event.type!r} at {event.at} + duration {event.duration} "
                f"exceeds timeline duration {total_duration}"
            )

    for event in sorted_events:
        if event.resolution is not None and event.resolution > config.resolution_seconds:
            raise ValueError(
                f"event {event.type!r} resolution ({event.resolution}s) is coarser "
                f"than global resolution ({config.resolution_seconds}s)"
            )

    for i in range(len(sorted_events) - 1):
        current = sorted_events[i]
        next_event = sorted_events[i + 1]
        current_end = current.at + current.duration + current.restart_gap
        if current_end > next_event.at:
            raise ValueError(
                f"events overlap: {current.type!r} ends at {current_end} "
                f"but {next_event.type!r} starts at {next_event.at}"
            )
