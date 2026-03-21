"""Prometheus shaper — downsamples profile data and expands into Prometheus metric rows."""

from __future__ import annotations

import math
from collections.abc import Iterator
from typing import Any

import pandas as pd

from slo_generator.constants import DURATION_BUCKETS
from slo_generator.shapers.base import BaseShaper

# Port for instance label format: service-host:port
_INSTANCE_PORT = 8080


def _lognormal_bucket_fractions(p50: float, p99: float) -> list[float]:
    """Compute cumulative histogram fractions for DURATION_BUCKETS using a log-normal approximation.

    Given p50 and p99, estimate the mu and sigma of the underlying log-normal distribution,
    then compute the CDF at each bucket boundary.  Returns a list of length len(DURATION_BUCKETS),
    each entry in [0, 1], strictly non-decreasing, with the last bucket representing +Inf (=1.0).
    """
    # Avoid log(0) if latency is 0 or negative
    p50 = max(p50, 1e-6)
    p99 = max(p99, p50)

    # Log-normal: mu = log(median), sigma derived from p99 = mu + z99 * sigma
    # z99 ≈ 2.326
    mu = math.log(p50)
    z99 = 2.3263478740408408
    sigma = (math.log(p99) - mu) / z99
    sigma = max(sigma, 1e-6)

    fractions: list[float] = []
    for le in DURATION_BUCKETS:
        # Standard normal CDF approximation via erf
        z = (math.log(le) - mu) / (sigma * math.sqrt(2))
        cdf = 0.5 * (1.0 + math.erf(z))
        fractions.append(min(max(cdf, 0.0), 1.0))
    return fractions


class PrometheusShaper(BaseShaper):
    """Shapes profile DataFrames into Prometheus-style metric rows.

    Downsamples to ``scrape_interval`` seconds, then expands each row into:
    - ``http_requests_total`` (cumulative counter, label: status_code=200)
    - ``http_errors_total`` (cumulative counter)
    - ``http_request_duration_seconds_bucket`` (one row per le bucket, cumulative)
    - ``http_request_duration_seconds_sum`` (cumulative)
    - ``http_request_duration_seconds_count`` (cumulative)
    - ``cpu_usage_percent`` (gauge)
    - ``memory_usage_bytes`` (gauge)

    Maintains cumulative counter accumulators keyed by (service, host) across calls to ``shape()``.
    """

    def __init__(self, scrape_interval: int = 30) -> None:
        self.scrape_interval = scrape_interval
        # Accumulators: key=(service, host), value=dict of metric->float
        self._accumulators: dict[tuple[str, str], dict[str, float]] = {}

    def shape(self, profile_chunk: pd.DataFrame) -> Iterator[pd.DataFrame]:
        """Downsample and expand profile_chunk into Prometheus metric rows."""
        chunk = profile_chunk.copy()
        chunk["timestamp"] = pd.to_datetime(chunk["timestamp"], utc=True)
        chunk = chunk.set_index("timestamp")

        # Group by service+host, then resample per group
        grouped = chunk.groupby(["service", "host"], observed=True)

        all_rows: list[dict[str, Any]] = []

        for (service, host), group_df in grouped:
            service = str(service)
            host = str(host)

            resampled = group_df.resample(f"{self.scrape_interval}s").agg(
                {
                    "throughput_rps": "mean",
                    "error_rate": "mean",
                    "p50_latency": "mean",
                    "p99_latency": "mean",
                    "cpu_percent": "last",
                    "memory_bytes": "last",
                }
            )
            resampled = resampled.dropna(how="all")

            key = (service, host)
            if key not in self._accumulators:
                self._accumulators[key] = {
                    "http_requests_total": 0.0,
                    "http_errors_total": 0.0,
                    "http_request_duration_seconds_sum": 0.0,
                    "http_request_duration_seconds_count": 0.0,
                    **{f"bucket_{i}": 0.0 for i in range(len(DURATION_BUCKETS))},
                }

            acc = self._accumulators[key]
            instance = f"{service}-{host}:{_INSTANCE_PORT}"

            for ts, row in resampled.iterrows():
                throughput = float(row["throughput_rps"]) * self.scrape_interval
                error_rate = float(row["error_rate"])
                p50 = float(row["p50_latency"])
                p99 = float(row["p99_latency"])

                errors = throughput * error_rate

                # Update cumulative counters
                acc["http_requests_total"] += throughput
                acc["http_errors_total"] += errors
                acc["http_request_duration_seconds_count"] += throughput
                acc["http_request_duration_seconds_sum"] += throughput * p50

                # Histogram bucket fractions
                fracs = _lognormal_bucket_fractions(p50, p99)
                for i, frac in enumerate(fracs):
                    acc[f"bucket_{i}"] += throughput * frac

                timestamp = ts.to_pydatetime()

                # Emit gauge metrics
                all_rows.append(
                    {
                        "timestamp": timestamp,
                        "metric": "cpu_usage_percent",
                        "value": float(row["cpu_percent"]),
                        "service": service,
                        "host": host,
                        "instance": instance,
                        "job": "app",
                        "le": pd.NA,
                        "status_code": pd.NA,
                    }
                )
                all_rows.append(
                    {
                        "timestamp": timestamp,
                        "metric": "memory_usage_bytes",
                        "value": float(row["memory_bytes"]),
                        "service": service,
                        "host": host,
                        "instance": instance,
                        "job": "app",
                        "le": pd.NA,
                        "status_code": pd.NA,
                    }
                )

                # Emit cumulative counter metrics
                all_rows.append(
                    {
                        "timestamp": timestamp,
                        "metric": "http_requests_total",
                        "value": acc["http_requests_total"],
                        "service": service,
                        "host": host,
                        "instance": instance,
                        "job": "app",
                        "le": pd.NA,
                        "status_code": "200",
                    }
                )
                all_rows.append(
                    {
                        "timestamp": timestamp,
                        "metric": "http_errors_total",
                        "value": acc["http_errors_total"],
                        "service": service,
                        "host": host,
                        "instance": instance,
                        "job": "app",
                        "le": pd.NA,
                        "status_code": pd.NA,
                    }
                )
                all_rows.append(
                    {
                        "timestamp": timestamp,
                        "metric": "http_request_duration_seconds_sum",
                        "value": acc["http_request_duration_seconds_sum"],
                        "service": service,
                        "host": host,
                        "instance": instance,
                        "job": "app",
                        "le": pd.NA,
                        "status_code": pd.NA,
                    }
                )
                all_rows.append(
                    {
                        "timestamp": timestamp,
                        "metric": "http_request_duration_seconds_count",
                        "value": acc["http_request_duration_seconds_count"],
                        "service": service,
                        "host": host,
                        "instance": instance,
                        "job": "app",
                        "le": pd.NA,
                        "status_code": pd.NA,
                    }
                )

                # Emit histogram bucket metrics
                for i, le_val in enumerate(DURATION_BUCKETS):
                    all_rows.append(
                        {
                            "timestamp": timestamp,
                            "metric": "http_request_duration_seconds_bucket",
                            "value": acc[f"bucket_{i}"],
                            "service": service,
                            "host": host,
                            "instance": instance,
                            "job": "app",
                            "le": str(le_val),
                            "status_code": pd.NA,
                        }
                    )
                # +Inf bucket = total count
                all_rows.append(
                    {
                        "timestamp": timestamp,
                        "metric": "http_request_duration_seconds_bucket",
                        "value": acc["http_request_duration_seconds_count"],
                        "service": service,
                        "host": host,
                        "instance": instance,
                        "job": "app",
                        "le": "+Inf",
                        "status_code": pd.NA,
                    }
                )

        if all_rows:
            yield pd.DataFrame(all_rows)

    def finalize(self) -> Iterator[pd.DataFrame]:
        """Flush remaining state — currently stateless flush, no pending buffered rows."""
        return iter([])
