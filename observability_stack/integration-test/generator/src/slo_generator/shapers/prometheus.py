"""Prometheus shaper — consumes RawChunk, uses MicrometerApp accumulation."""

from __future__ import annotations

import math
from collections.abc import Iterator
from typing import Any

import pandas as pd

from slo_generator.generator_config import GeneratorConfig
from slo_generator.micrometer import MicrometerApp
from slo_generator.raw import RawChunk
from slo_generator.shapers.base import BaseShaper

_INSTANCE_PORT = 8080


class PrometheusShaper(BaseShaper):
    """Shapes RawChunk into Prometheus-style metric rows using MicrometerApp.

    Maintains one MicrometerApp per (service, host). For each second of raw data,
    accumulates into the app. At scrape interval boundaries, emits a snapshot.

    Output DataFrame columns:
        timestamp, metric, value, service, host, instance, job, le, status_code
    """

    def __init__(self, config: GeneratorConfig | None = None) -> None:
        self.config = config or GeneratorConfig.default()
        self._apps: dict[tuple[str, str], MicrometerApp] = {}
        self._last_scrape_epoch: dict[tuple[str, str], float] = {}

    def _get_app(self, service: str, host: str) -> MicrometerApp:
        key = (service, host)
        if key not in self._apps:
            self._apps[key] = MicrometerApp(buckets_ms=list(self.config.histogram_buckets_ms))
            self._last_scrape_epoch[key] = 0.0
        return self._apps[key]

    def shape(self, raw_chunk: RawChunk) -> Iterator[pd.DataFrame]:
        """Feed raw samples into MicrometerApps, emit at scrape boundaries."""
        # Group samples by (service, host) and sort by timestamp
        by_key: dict[tuple[str, str], list] = {}
        for sample in raw_chunk:
            key = (sample.service, sample.host)
            by_key.setdefault(key, []).append(sample)

        all_rows: list[dict[str, Any]] = []

        for (service, host), samples in by_key.items():
            samples.sort(key=lambda s: s.timestamp)
            app = self._get_app(service, host)
            key = (service, host)
            instance = f"{service}-{host}:{_INSTANCE_PORT}"

            for sample in samples:
                app.record_second(sample)

                epoch = sample.timestamp.timestamp()
                last = self._last_scrape_epoch[key]
                interval = self.config.scrape_interval_s

                # Emit at scrape interval boundaries
                if last == 0.0 or epoch - last >= interval:
                    self._last_scrape_epoch[key] = epoch
                    snap = app.scrape(epoch)
                    timestamp = sample.timestamp

                    # Gauges
                    all_rows.append(
                        _row(
                            timestamp,
                            "cpu_usage_percent",
                            snap.cpu_percent,
                            service,
                            host,
                            instance,
                        )
                    )
                    all_rows.append(
                        _row(
                            timestamp,
                            "memory_usage_bytes",
                            snap.memory_bytes,
                            service,
                            host,
                            instance,
                        )
                    )

                    # Cumulative counters
                    all_rows.append(
                        _row(
                            timestamp,
                            "http_requests_total",
                            snap.request_counter,
                            service,
                            host,
                            instance,
                            status_code="200",
                        )
                    )
                    all_rows.append(
                        _row(
                            timestamp,
                            "http_errors_total",
                            snap.error_counter,
                            service,
                            host,
                            instance,
                        )
                    )

                    # Histogram sum and count
                    sum_seconds = snap.sum_ms / 1000.0
                    all_rows.append(
                        _row(
                            timestamp,
                            "http_request_duration_seconds_sum",
                            sum_seconds,
                            service,
                            host,
                            instance,
                        )
                    )
                    all_rows.append(
                        _row(
                            timestamp,
                            "http_request_duration_seconds_count",
                            snap.count,
                            service,
                            host,
                            instance,
                        )
                    )

                    # Histogram buckets
                    for i, le_ms in enumerate(snap.buckets_ms):
                        if math.isinf(le_ms):
                            le_str = "+Inf"
                        else:
                            le_seconds = le_ms / 1000.0
                            le_str = f"{le_seconds:g}"
                        all_rows.append(
                            _row(
                                timestamp,
                                "http_request_duration_seconds_bucket",
                                snap.bucket_counts[i],
                                service,
                                host,
                                instance,
                                le=le_str,
                            )
                        )

        if all_rows:
            yield pd.DataFrame(all_rows)

    def finalize(self) -> Iterator[pd.DataFrame]:
        """No buffered state to flush."""
        return iter([])


def _row(
    timestamp: Any,
    metric: str,
    value: float,
    service: str,
    host: str,
    instance: str,
    *,
    le: Any = pd.NA,
    status_code: Any = pd.NA,
) -> dict[str, Any]:
    return {
        "timestamp": timestamp,
        "metric": metric,
        "value": value,
        "service": service,
        "host": host,
        "instance": instance,
        "job": "app",
        "le": le,
        "status_code": status_code,
    }
