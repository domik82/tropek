"""Base scenario — defines the interface all scenarios implement."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
from models import (
    DURATION_BUCKETS,
    MetricFamily,
    MetricType,
    Sample,
)


@dataclass
class ServiceProfile:
    """Operational profile for one (service, host) combination at a point in time."""

    service: str
    host: str

    # Request throughput (requests/second)
    throughput_rps: float = 100.0

    # Error rate (fraction 0.0–1.0)
    error_rate: float = 0.001

    # Latency percentiles (seconds)
    p50_latency: float = 0.020  # 20ms
    p99_latency: float = 0.080  # 80ms

    # Resource utilisation (0–100 for CPU, bytes for memory)
    cpu_percent: float = 40.0
    memory_bytes: float = 512 * 1024 * 1024  # 512 MB


# Services and hosts used across all scenarios
SERVICES = ["frontend", "api", "backend"]
HOSTS_PER_SERVICE = ["host1", "host2"]

# Baseline healthy profile (used as default)
HEALTHY_PROFILE = ServiceProfile(
    service="",  # filled per service/host
    host="",
    throughput_rps=100.0,
    error_rate=0.001,
    p50_latency=0.020,
    p99_latency=0.080,
    cpu_percent=40.0,
    memory_bytes=512 * 1024 * 1024,
)


class BaseScenario(ABC):
    """Abstract base for all data generation scenarios.

    Each scenario implements `profile_at(t, service, host)` which returns
    a ServiceProfile describing the operational state at time t.
    The base class handles the actual sample generation loop.
    """

    name: str = "base"
    description: str = ""

    def __init__(self, start: datetime, end: datetime, resolution_seconds: int = 30):
        self.start = start
        self.end = end
        self.resolution = timedelta(seconds=resolution_seconds)
        self._rng = np.random.default_rng(seed=42)  # reproducible noise

    @abstractmethod
    def profile_at(self, t: datetime, service: str, host: str) -> ServiceProfile:
        """Return the operational profile for this service/host at time t."""
        ...

    def timestamps(self) -> Iterator[datetime]:
        t = self.start
        while t <= self.end:
            yield t
            t += self.resolution

    # ── Sample generators ────────────────────────────────────────────────

    def generate(self) -> dict[str, MetricFamily]:
        """Generate all metric families for this scenario.
        Returns a dict of metric_name → MetricFamily.
        """
        families = self._init_families()

        # Per-(service, host) counter accumulators (counters must be monotonic)
        req_acc: dict[tuple, float] = {}
        err_acc: dict[tuple, float] = {}
        hist_acc: dict[tuple, dict] = {}  # (service,host,le) -> cumulative count
        hist_sum_acc: dict[tuple, float] = {}
        hist_count_acc: dict[tuple, float] = {}

        for t in self.timestamps():
            for service in SERVICES:
                for host in HOSTS_PER_SERVICE:
                    p = self.profile_at(t, service, host)
                    labels = {"service": service, "host": host}

                    # ── counters: accumulate delta over resolution window ──
                    key = (service, host)
                    delta_reqs = p.throughput_rps * self.resolution.total_seconds()
                    delta_errs = p.throughput_rps * p.error_rate * self.resolution.total_seconds()

                    req_acc[key] = (
                        req_acc.get(key, 0.0) + delta_reqs + self._jitter(delta_reqs, 0.02)
                    )
                    err_acc[key] = (
                        err_acc.get(key, 0.0) + delta_errs + self._jitter(delta_errs, 0.05)
                    )

                    families["http_requests_total"].add(
                        Sample(
                            timestamp=t,
                            value=req_acc[key],
                            labels={**labels, "status_code": "200"},
                        )
                    )
                    families["http_errors_total"].add(
                        Sample(
                            timestamp=t,
                            value=err_acc[key],
                            labels=labels,
                        )
                    )

                    # ── histogram ──────────────────────────────────────────
                    hist_key = (service, host)
                    interval_count = delta_reqs
                    p50 = p.p50_latency * (1 + self._jitter(1, 0.05))
                    p99 = p.p99_latency * (1 + self._jitter(1, 0.08))

                    # Accumulate bucket counts
                    for bucket in DURATION_BUCKETS + [float("+inf")]:
                        frac = self._bucket_fraction(bucket, p50, p99)
                        bkey = (service, host, str(bucket) if bucket != float("+inf") else "+Inf")
                        hist_acc[bkey] = hist_acc.get(bkey, 0.0) + interval_count * frac

                    avg_latency = (p50 + p99) / 2
                    hist_sum_acc[hist_key] = (
                        hist_sum_acc.get(hist_key, 0.0) + avg_latency * interval_count
                    )
                    hist_count_acc[hist_key] = hist_count_acc.get(hist_key, 0.0) + interval_count

                    for bucket in DURATION_BUCKETS:
                        bkey = (service, host, str(bucket))
                        families["http_request_duration_seconds_bucket"].add(
                            Sample(
                                timestamp=t,
                                value=hist_acc[bkey],
                                labels={**labels, "le": str(bucket)},
                            )
                        )
                    bkey_inf = (service, host, "+Inf")
                    families["http_request_duration_seconds_bucket"].add(
                        Sample(
                            timestamp=t,
                            value=hist_acc[bkey_inf],
                            labels={**labels, "le": "+Inf"},
                        )
                    )
                    families["http_request_duration_seconds_sum"].add(
                        Sample(
                            timestamp=t,
                            value=hist_sum_acc[hist_key],
                            labels=labels,
                        )
                    )
                    families["http_request_duration_seconds_count"].add(
                        Sample(
                            timestamp=t,
                            value=hist_count_acc[hist_key],
                            labels=labels,
                        )
                    )

                    # ── gauges ─────────────────────────────────────────────
                    cpu = max(0.0, min(100.0, p.cpu_percent + self._jitter(p.cpu_percent, 0.03)))
                    mem = max(0.0, p.memory_bytes + self._jitter(p.memory_bytes, 0.02))

                    families["cpu_usage_percent"].add(
                        Sample(
                            timestamp=t,
                            value=cpu,
                            labels=labels,
                        )
                    )
                    families["memory_usage_bytes"].add(
                        Sample(
                            timestamp=t,
                            value=mem,
                            labels=labels,
                        )
                    )

        return families

    # ── Helpers ──────────────────────────────────────────────────────────

    def _jitter(self, value: float, fraction: float) -> float:
        """Add ±fraction of value as random noise."""
        return float(self._rng.normal(0, value * fraction))

    @staticmethod
    def _bucket_fraction(le: float, p50: float, p99: float) -> float:
        """Fraction of requests that fall within this histogram bucket."""
        if le == float("+inf"):
            return 1.0
        if le <= p50 * 0.3:
            return 0.10
        elif le <= p50:
            return 0.50
        elif le <= p99 * 0.7:
            return 0.80
        elif le <= p99:
            return 0.99
        elif le <= p99 * 2:
            return 0.999
        else:
            return 0.9999

    @staticmethod
    def _init_families() -> dict[str, MetricFamily]:
        return {
            "http_requests_total": MetricFamily(
                "http_requests_total", MetricType.COUNTER, "Total HTTP requests"
            ),
            "http_errors_total": MetricFamily(
                "http_errors_total", MetricType.COUNTER, "Total HTTP errors"
            ),
            "http_request_duration_seconds_bucket": MetricFamily(
                "http_request_duration_seconds_bucket",
                MetricType.HISTOGRAM,
                "HTTP request duration histogram buckets",
            ),
            "http_request_duration_seconds_sum": MetricFamily(
                "http_request_duration_seconds_sum", MetricType.COUNTER, "HTTP request duration sum"
            ),
            "http_request_duration_seconds_count": MetricFamily(
                "http_request_duration_seconds_count",
                MetricType.COUNTER,
                "HTTP request duration count",
            ),
            "cpu_usage_percent": MetricFamily(
                "cpu_usage_percent", MetricType.GAUGE, "CPU usage percent (0-100)"
            ),
            "memory_usage_bytes": MetricFamily(
                "memory_usage_bytes", MetricType.GAUGE, "Memory usage in bytes"
            ),
        }
