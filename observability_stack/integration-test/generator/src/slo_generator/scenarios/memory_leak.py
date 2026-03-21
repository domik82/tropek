"""Memory leak scenario — exponential latency growth over days/weeks until crash."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from slo_generator.constants import HEALTHY_DEFAULTS, HOST_FACTORS, SERVICE_FACTORS
from slo_generator.scenarios.base import BaseScenario


class MemoryLeakScenario(BaseScenario):
    """Simulates a slow memory leak causing exponential latency degradation."""

    name = "memory_leak"

    def __init__(
        self,
        start: datetime,
        end: datetime,
        *,
        event_mode: bool = True,
        growth_rate: float = 0.003,
        crash_at_end: bool = True,
    ):
        super().__init__(start, end, event_mode=event_mode)
        self.growth_rate = growth_rate
        self.crash_at_end = crash_at_end

    def _build_profiles(
        self,
        timestamps: pd.DatetimeIndex,
        service: str,
        host: str,
    ) -> pd.DataFrame:
        sf = SERVICE_FACTORS.get(service, 1.0)
        hf = HOST_FACTORS.get(host, 1.0)
        base = HEALTHY_DEFAULTS

        total_seconds = (self.end - self.start).total_seconds()
        ts_epoch = timestamps.astype(np.int64) / 1e9
        start_epoch = self.start.timestamp()

        # Normalized progress 0->1 over the event window
        progress = np.clip((ts_epoch - start_epoch) / total_seconds, 0.0, 1.0)

        # Exponential growth: e^(growth_rate * 100 * progress)
        # growth_rate=0.003 → mild 1.35x peak; growth_rate=0.01 → aggressive 2.7x peak
        growth = np.exp(self.growth_rate * 100.0 * progress)

        # Latency grows exponentially
        p50 = base["p50_latency"] * growth
        p99 = base["p99_latency"] * growth

        # Memory grows linearly toward 95% of a notional 2GB limit
        max_memory = 2 * 1024 * 1024 * 1024 * 0.95
        base_mem = base["memory_bytes"] * hf
        memory = base_mem + progress * (max_memory - base_mem)

        # Throughput decreases as GC pressure mounts
        throughput = np.maximum(
            10.0,
            base["throughput_rps"] * sf * hf * (1.0 - 0.3 * progress),
        )

        # Error rate stays low until later phases
        error_rate = np.where(
            progress < 0.8,
            base["error_rate"],
            base["error_rate"] + (progress - 0.8) * 5 * 0.1,
        )

        # CPU increases with memory pressure
        cpu = np.clip(base["cpu_percent"] + progress * 30, 0.0, 100.0)

        # Crash phase: final hour
        if self.crash_at_end:
            crash_threshold = 1.0 - (3600 / total_seconds)  # last hour
            crash_mask = progress >= crash_threshold
            crash_progress = np.clip(
                (progress - crash_threshold) / (1.0 - crash_threshold), 0.0, 1.0
            )
            throughput = np.where(
                crash_mask, np.maximum(0.1, 10 * (1 - crash_progress)), throughput
            )
            error_rate = np.where(
                crash_mask, np.minimum(1.0, 0.5 + 0.5 * crash_progress), error_rate
            )
            p99 = np.where(crash_mask, 30.0, p99)  # timeout
            p50 = np.where(crash_mask, 10.0, p50)
            cpu = np.where(crash_mask, 99.0, cpu)

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
