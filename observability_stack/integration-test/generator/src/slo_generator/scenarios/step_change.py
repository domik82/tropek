"""Step change scenario — sustained level shift after config change or capacity reduction."""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from slo_generator.constants import HEALTHY_DEFAULTS, HOST_FACTORS, SERVICE_FACTORS
from slo_generator.scenarios.base import BaseScenario


class StepChangeScenario(BaseScenario):
    """Simulates a sustained level shift with brief ramp to new baseline."""

    name = "step_change"

    def __init__(
        self,
        start: datetime,
        end: datetime,
        *,
        event_mode: bool = True,
        latency_multiplier: float = 1.5,
        throughput_multiplier: float = 1.0,
        error_rate_multiplier: float = 1.0,
        ramp_minutes: int = 2,
    ):
        super().__init__(start, end, event_mode=event_mode)
        self.lat_mult = latency_multiplier
        self.tput_mult = throughput_multiplier
        self.err_mult = error_rate_multiplier
        self.ramp_end = start + timedelta(minutes=ramp_minutes)

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

        ts_epoch = timestamps.astype(np.int64) / 1e9
        start_epoch = self.start.timestamp()
        ramp_end_epoch = self.ramp_end.timestamp()
        ramp_duration = (self.ramp_end - self.start).total_seconds()

        ramp_frac = np.clip((ts_epoch - start_epoch) / max(ramp_duration, 1.0), 0.0, 1.0)

        is_ramping = ts_epoch < ramp_end_epoch

        def interpolate(base_val: float, multiplier: float) -> np.ndarray:
            target = base_val * multiplier
            return np.where(is_ramping, base_val + ramp_frac * (target - base_val), target)

        throughput = np.maximum(10.0, interpolate(base["throughput_rps"] * sf * hf, self.tput_mult))
        error_rate = np.clip(interpolate(base["error_rate"], self.err_mult), 0.0, 1.0)
        p50 = interpolate(base["p50_latency"], self.lat_mult)
        p99 = interpolate(base["p99_latency"], self.lat_mult)
        cpu = np.clip(interpolate(base["cpu_percent"], self.lat_mult * 0.8), 0.0, 100.0)

        return pd.DataFrame(
            {
                "timestamp": timestamps,
                "throughput_rps": throughput,
                "error_rate": error_rate,
                "p50_latency": p50,
                "p99_latency": p99,
                "cpu_percent": cpu,
                "memory_bytes": np.full(n, base["memory_bytes"] * hf),
            }
        )
