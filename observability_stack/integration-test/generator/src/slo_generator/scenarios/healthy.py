"""Healthy scenario — everything is normal, mild diurnal variation."""

from __future__ import annotations

import numpy as np
import pandas as pd

from slo_generator.constants import HEALTHY_DEFAULTS, HOST_FACTORS, SERVICE_FACTORS
from slo_generator.scenarios.base import BaseScenario


class HealthyScenario(BaseScenario):
    """Simulates a healthy system with mild diurnal variation (~±15%)."""

    name = "healthy"

    def _build_profiles(
        self,
        timestamps: pd.DatetimeIndex,
        service: str,
        host: str,
    ) -> pd.DataFrame:
        n = len(timestamps)
        hours = timestamps.hour + timestamps.minute / 60
        diurnal = 1.0 + 0.15 * np.sin(2 * np.pi * (hours / 24 - 0.25))

        sf = SERVICE_FACTORS.get(service, 1.0)
        hf = HOST_FACTORS.get(host, 1.0)

        base_throughput = HEALTHY_DEFAULTS["throughput_rps"] * sf * hf
        throughput = np.maximum(10.0, base_throughput * diurnal)

        cpu_base = HEALTHY_DEFAULTS["cpu_percent"]
        cpu = np.clip(
            cpu_base * (0.8 + 0.4 * (throughput / (HEALTHY_DEFAULTS["throughput_rps"] * sf))),
            0.0,
            100.0,
        )

        return pd.DataFrame(
            {
                "timestamp": timestamps,
                "throughput_rps": throughput,
                "error_rate": np.full(n, HEALTHY_DEFAULTS["error_rate"]),
                "p50_latency": np.full(n, HEALTHY_DEFAULTS["p50_latency"]),
                "p99_latency": np.full(n, HEALTHY_DEFAULTS["p99_latency"]),
                "cpu_percent": cpu,
                "memory_bytes": np.full(n, HEALTHY_DEFAULTS["memory_bytes"] * hf),
            }
        )
