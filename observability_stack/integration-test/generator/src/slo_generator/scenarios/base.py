"""Base scenario — defines the interface all scenarios implement."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import numpy as np

from slo_generator.constants import HOSTS, SERVICES
from slo_generator.generator_config import GeneratorConfig
from slo_generator.raw import RawChunk


def _generate_timestamps(
    start: datetime,
    end: datetime,
    resolution_seconds: int,
) -> list[datetime]:
    """Generate a list of timestamps from start (inclusive) to end (exclusive)."""
    if start >= end:
        return []
    timestamps: list[datetime] = []
    current = start if start.tzinfo else start.replace(tzinfo=UTC)
    end_utc = end if end.tzinfo else end.replace(tzinfo=UTC)
    delta = timedelta(seconds=resolution_seconds)
    while current < end_utc:
        timestamps.append(current)
        current += delta
    return timestamps


class BaseScenario(ABC):
    """Abstract base for all data generation scenarios."""

    name: str = "base"

    def __init__(
        self,
        start: datetime,
        end: datetime,
        *,
        config: GeneratorConfig | None = None,
        event_mode: bool = False,
    ):
        self.start = start
        self.end = end
        self.event_mode = event_mode
        self.config = config or GeneratorConfig.default()
        self._rng = np.random.default_rng(seed=self.config.seed)

    def generate(
        self,
        resolution_seconds: int = 1,
        chunk_hours: int = 1,
    ) -> Iterator[RawChunk]:
        """Yield RawChunk lists in hour-sized chunks."""
        chunk_delta = timedelta(hours=chunk_hours)
        chunk_start = self.start

        while chunk_start < self.end:
            chunk_end = min(chunk_start + chunk_delta, self.end)
            timestamps = _generate_timestamps(chunk_start, chunk_end, resolution_seconds)
            if not timestamps:
                chunk_start = chunk_end
                continue

            chunk = self._build_chunk(timestamps)
            yield chunk
            chunk_start = chunk_end

    def generate_window(
        self,
        window_start: datetime,
        window_end: datetime,
        resolution_seconds: int = 1,
    ) -> RawChunk:
        """Generate a single RawChunk for an arbitrary sub-window.

        Unlike generate() which yields hour-sized chunks over the full range,
        this returns one RawChunk covering exactly [window_start, window_end)
        at the given resolution. Used by the composer for event splicing.
        """
        timestamps = _generate_timestamps(window_start, window_end, resolution_seconds)
        if not timestamps:
            return []
        return self._build_chunk(timestamps)

    def _build_chunk(self, timestamps: list[datetime]) -> RawChunk:
        """Build a RawChunk for one chunk by combining all service-host combos."""
        samples: RawChunk = []
        for service in SERVICES:
            for host in HOSTS:
                samples.extend(self._build_raw_samples(timestamps, service, host))
        return samples

    @abstractmethod
    def _build_raw_samples(
        self,
        timestamps: list[datetime],
        service: str,
        host: str,
    ) -> RawChunk:
        """Build raw samples for one (service, host) across all timestamps in chunk.

        Must return a list of RawSample objects, one per timestamp.
        """
        ...
