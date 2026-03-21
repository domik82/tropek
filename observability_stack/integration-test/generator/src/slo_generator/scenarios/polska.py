"""Polska scenario — easter egg using Poland's geographic contour as metric envelope."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from slo_generator.constants import HEALTHY_DEFAULTS, HOST_FACTORS, SERVICE_FACTORS
from slo_generator.scenarios.base import BaseScenario
from slo_generator.scenarios.polska_contour import POLSKA_LOWER, POLSKA_UPPER, POLSKA_X


class PolskaScenario(BaseScenario):
    """Generates metrics shaped like Poland's geographic contour."""

    name = "polska"

    def __init__(
        self,
        start: datetime,
        end: datetime,
        *,
        event_mode: bool = True,
        noise_amplitude: float = 0.05,
        throughput_range: tuple[float, float] = (50.0, 200.0),
        latency_range: tuple[float, float] = (0.01, 0.5),
    ):
        super().__init__(start, end, event_mode=event_mode)
        self.noise_amplitude = noise_amplitude
        self.throughput_range = throughput_range
        self.latency_range = latency_range

    def _build_profiles(
        self,
        timestamps: pd.DatetimeIndex,
        service: str,
        host: str,
    ) -> pd.DataFrame:
        n = len(timestamps)
        sf = SERVICE_FACTORS.get(service, 1.0)
        hf = HOST_FACTORS.get(host, 1.0)
        base = HEALTHY_DEFAULTS

        total_seconds = (self.end - self.start).total_seconds()
        ts_epoch = timestamps.astype(np.int64) / 1e9
        start_epoch = self.start.timestamp()
        progress = np.clip((ts_epoch - start_epoch) / total_seconds, 0.0, 1.0)

        # Interpolate contour values at each timestamp's progress
        upper = np.interp(progress, POLSKA_X, POLSKA_UPPER)
        lower = np.interp(progress, POLSKA_X, POLSKA_LOWER)

        # Add noise
        noise_t = self._rng.normal(0, self.noise_amplitude, n)
        noise_l = self._rng.normal(0, self.noise_amplitude, n)

        # Map upper contour -> throughput
        tmin, tmax = self.throughput_range
        throughput = np.clip(
            tmin + (upper + noise_t) * (tmax - tmin) * sf * hf,
            10.0,
            tmax * 2,
        )

        # Map lower contour -> latency (inverted: lower contour = higher latency)
        lmin, lmax = self.latency_range
        p99 = np.clip(
            lmin + (1.0 - lower + noise_l) * (lmax - lmin),
            lmin,
            lmax * 2,
        )
        p50 = p99 * 0.3

        # Derived metrics
        error_rate = np.full(n, base["error_rate"])
        cpu = np.clip(30 + upper * 40, 0.0, 100.0)
        memory = np.full(n, base["memory_bytes"] * hf)

        return pd.DataFrame(
            {
                "timestamp": timestamps,
                "throughput_rps": throughput,
                "error_rate": error_rate,
                "p50_latency": p50,
                "p99_latency": p99,
                "cpu_percent": cpu,
                "memory_bytes": memory,
            }
        )
