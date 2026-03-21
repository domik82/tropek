"""Base scenario — defines the interface all scenarios implement."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from slo_generator.constants import HOSTS, PROFILE_COLUMNS, SERVICES


class BaseScenario(ABC):
    """Abstract base for all data generation scenarios."""

    name: str = "base"

    def __init__(self, start: datetime, end: datetime):
        self.start = start
        self.end = end
        self._rng = np.random.default_rng(seed=42)

    def generate(
        self,
        resolution_seconds: int = 1,
        chunk_hours: int = 1,
    ) -> Iterator[pd.DataFrame]:
        """Yield profile DataFrames in hour-sized chunks."""
        chunk_delta = timedelta(hours=chunk_hours)
        chunk_start = self.start

        while chunk_start < self.end:
            chunk_end = min(chunk_start + chunk_delta, self.end)
            timestamps = pd.date_range(
                chunk_start,
                chunk_end,
                freq=f"{resolution_seconds}s",
                inclusive="left",
                tz="UTC",
            ).as_unit("ns")
            if len(timestamps) == 0:
                chunk_start = chunk_end
                continue

            df = self._build_chunk(timestamps)
            yield df
            chunk_start = chunk_end

    def _build_chunk(self, timestamps: pd.DatetimeIndex) -> pd.DataFrame:
        """Build a profile DataFrame for one chunk by combining all service-host combos."""
        frames: list[pd.DataFrame] = []
        for service in SERVICES:
            for host in HOSTS:
                profiles = self._build_profiles(timestamps, service, host)
                profiles["service"] = pd.Categorical(
                    [service] * len(timestamps), categories=SERVICES
                )
                profiles["host"] = pd.Categorical([host] * len(timestamps), categories=HOSTS)
                frames.append(profiles)

        df = pd.concat(frames, ignore_index=True)
        return df[PROFILE_COLUMNS]

    @abstractmethod
    def _build_profiles(
        self,
        timestamps: pd.DatetimeIndex,
        service: str,
        host: str,
    ) -> pd.DataFrame:
        """Build profile values for one (service, host) across all timestamps in chunk.

        Must return a DataFrame with columns: timestamp, throughput_rps, error_rate,
        p50_latency, p99_latency, cpu_percent, memory_bytes.
        (service and host are added by the base class.)
        """
        ...
