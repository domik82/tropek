"""Degradation scenario — deployment regression with visible latency increase."""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from slo_generator.constants import HEALTHY_DEFAULTS, SERVICE_FACTORS
from slo_generator.scenarios.base import BaseScenario


class DegradationScenario(BaseScenario):
    """Simulates a bad deployment: latency 5x, error rate 5x, throughput unchanged."""

    name = "degradation"

    def __init__(
        self,
        start: datetime,
        end: datetime,
        *,
        event_mode: bool = False,
        ramp_minutes: int = 5,
        latency_multiplier: float = 5.0,
        error_rate_multiplier: float = 5.0,
    ):
        super().__init__(start, end, event_mode=event_mode)
        if event_mode:
            self.deploy_start = start
        else:
            total = (end - start).total_seconds()
            self.deploy_start = start + timedelta(seconds=total * 0.65)
        self.ramp_end = self.deploy_start + timedelta(minutes=ramp_minutes)
        self.lat_mult = latency_multiplier
        self.err_mult = error_rate_multiplier

    def _build_profiles(
        self,
        timestamps: pd.DatetimeIndex,
        service: str,
        host: str,
    ) -> pd.DataFrame:
        n = len(timestamps)
        sf = SERVICE_FACTORS.get(service, 1.0)
        base = HEALTHY_DEFAULTS

        ts_epoch = timestamps.astype(np.int64) / 1e9
        deploy_epoch = self.deploy_start.timestamp()
        ramp_end_epoch = self.ramp_end.timestamp()
        ramp_duration = (self.ramp_end - self.deploy_start).total_seconds()

        pre = ts_epoch < deploy_epoch
        ramp = (ts_epoch >= deploy_epoch) & (ts_epoch < ramp_end_epoch)

        ramp_frac = np.clip((ts_epoch - deploy_epoch) / ramp_duration, 0.0, 1.0)

        p99 = np.where(
            pre,
            base["p99_latency"],
            np.where(
                ramp,
                base["p99_latency"] * (1 + ramp_frac * (self.lat_mult - 1)),
                base["p99_latency"] * self.lat_mult,
            ),
        )

        p50 = np.where(
            pre,
            base["p50_latency"],
            np.where(
                ramp,
                np.maximum(
                    base["p50_latency"],
                    base["p50_latency"] * (1 + ramp_frac * (self.lat_mult * 0.5 - 1)),
                ),
                base["p50_latency"] * self.lat_mult * 0.5,
            ),
        )

        error_rate = np.where(
            pre,
            base["error_rate"],
            np.where(
                ramp,
                base["error_rate"] * (1 + ramp_frac * (self.err_mult - 1)),
                base["error_rate"] * self.err_mult,
            ),
        )

        cpu = np.where(
            pre,
            base["cpu_percent"],
            np.where(
                ramp,
                np.minimum(100.0, base["cpu_percent"] * (1 + ramp_frac * 0.35)),
                np.minimum(100.0, base["cpu_percent"] * 1.35),
            ),
        )

        return pd.DataFrame(
            {
                "timestamp": timestamps,
                "throughput_rps": np.full(n, base["throughput_rps"] * sf),
                "error_rate": error_rate,
                "p50_latency": p50,
                "p99_latency": p99,
                "cpu_percent": cpu,
                "memory_bytes": np.full(n, base["memory_bytes"]),
            }
        )
