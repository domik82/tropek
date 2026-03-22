"""MicrometerApp — cumulative counter + histogram bucket accumulation.

Ports the reference implementation from docs/micrometer/micrometer_prometheus_sim.py
into a reusable class that consumes RawSample objects.
"""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass

from slo_generator.generator_config import MICROMETER_BUCKETS_MS
from slo_generator.raw import RawSample


@dataclass
class ScrapeSnapshot:
    """A single Prometheus scrape result — what lands in the TSDB."""

    timestamp_epoch: float
    service: str
    host: str
    request_counter: int
    error_counter: int
    sum_ms: float
    count: int
    bucket_counts: list[int]
    buckets_ms: list[float]
    cpu_percent: float
    memory_bytes: float


class MicrometerApp:
    """Simulates Micrometer's PrometheusMeterRegistry accumulation.

    Maintains cumulative counters and histogram bucket counts for a single
    (service, host) combination. State only ever increases (like a real app).

    Args:
        buckets_ms: Histogram bucket boundaries in milliseconds.
            Defaults to Micrometer's standard set. +Inf is always appended.
    """

    def __init__(self, buckets_ms: list[float] | None = None):
        raw = buckets_ms if buckets_ms is not None else list(MICROMETER_BUCKETS_MS)
        self.buckets_ms: list[float] = sorted(b for b in raw if not math.isinf(b))
        self.buckets_ms.append(float("inf"))

        self._request_counter: int = 0
        self._error_counter: int = 0
        self._sum_ms: float = 0.0
        self._count: int = 0
        self._bucket_counts: list[int] = [0] * len(self.buckets_ms)

        self._last_cpu: float = 0.0
        self._last_memory: float = 0.0
        self._service: str = ""
        self._host: str = ""

    def record_second(self, sample: RawSample) -> None:
        """Accumulate one second of raw data into counters and buckets."""
        self._service = sample.service
        self._host = sample.host

        self._request_counter += sample.request_count
        self._error_counter += sample.error_count

        for lat in sample.latencies_ms:
            self._sum_ms += lat
            self._count += 1
            idx = bisect.bisect_left(self.buckets_ms, lat)
            for i in range(idx, len(self.buckets_ms)):
                self._bucket_counts[i] += 1

        self._last_cpu = sample.cpu_percent
        self._last_memory = sample.memory_bytes

    def scrape(self, timestamp_epoch: float) -> ScrapeSnapshot:
        """Read current cumulative state — no mutation."""
        return ScrapeSnapshot(
            timestamp_epoch=timestamp_epoch,
            service=self._service,
            host=self._host,
            request_counter=self._request_counter,
            error_counter=self._error_counter,
            sum_ms=self._sum_ms,
            count=self._count,
            bucket_counts=list(self._bucket_counts),
            buckets_ms=list(self.buckets_ms),
            cpu_percent=self._last_cpu,
            memory_bytes=self._last_memory,
        )
