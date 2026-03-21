"""Outage scenario — sudden failure affecting all services."""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from slo_generator.constants import HEALTHY_DEFAULTS, SERVICE_FACTORS
from slo_generator.scenarios.base import BaseScenario


class OutageScenario(BaseScenario):
    """Simulates a full outage: high errors, low throughput, high latency."""

    name = "outage"

    def __init__(
        self,
        start: datetime,
        end: datetime,
        outage_duration_minutes: int = 30,
        recovery_minutes: int = 10,
    ):
        super().__init__(start, end)
        total = (end - start).total_seconds()
        self.outage_start = start + timedelta(seconds=total * 0.60)
        self.outage_end = self.outage_start + timedelta(minutes=outage_duration_minutes)
        self.recovery_end = self.outage_end + timedelta(minutes=recovery_minutes)

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
        outage_start_epoch = self.outage_start.timestamp()
        outage_end_epoch = self.outage_end.timestamp()
        recovery_end_epoch = self.recovery_end.timestamp()

        # Phase masks
        pre = ts_epoch < outage_start_epoch
        outage = (ts_epoch >= outage_start_epoch) & (ts_epoch < outage_end_epoch)
        recovery = (ts_epoch >= outage_end_epoch) & (ts_epoch < recovery_end_epoch)

        # Ramp fraction during outage (0→1 over 2 minutes)
        ramp = np.clip((ts_epoch - outage_start_epoch) / 120.0, 0.0, 1.0)

        # Recovery fraction (0→1 over recovery window)
        rec_duration = (self.recovery_end - self.outage_end).total_seconds()
        rec_frac = np.clip((ts_epoch - outage_end_epoch) / rec_duration, 0.0, 1.0)

        throughput = np.where(
            pre,
            base["throughput_rps"] * sf,
            np.where(
                outage,
                np.maximum(2.0, base["throughput_rps"] * sf * (1 - ramp * 0.90)),
                np.where(
                    recovery,
                    np.maximum(10.0, 2.0 + rec_frac * (base["throughput_rps"] * sf - 2.0)),
                    base["throughput_rps"] * sf,
                ),
            ),
        )

        error_rate = np.where(
            pre,
            base["error_rate"],
            np.where(
                outage,
                np.minimum(0.95, base["error_rate"] + ramp * 0.79),
                np.where(
                    recovery,
                    np.maximum(base["error_rate"], 0.95 - rec_frac * (0.95 - base["error_rate"])),
                    base["error_rate"],
                ),
            ),
        )

        p99 = np.where(
            pre,
            base["p99_latency"],
            np.where(
                outage,
                base["p99_latency"] + ramp * 9.92,
                np.where(
                    recovery,
                    np.maximum(base["p99_latency"], 10.0 - rec_frac * (10.0 - base["p99_latency"])),
                    base["p99_latency"],
                ),
            ),
        )

        p50 = np.where(
            pre,
            base["p50_latency"],
            np.where(
                outage,
                base["p50_latency"] * (1 + ramp * 5),
                np.where(
                    recovery,
                    np.maximum(
                        base["p50_latency"],
                        base["p50_latency"] * (1 + (1 - rec_frac) * 5),
                    ),
                    base["p50_latency"],
                ),
            ),
        )

        cpu = np.where(
            pre,
            base["cpu_percent"],
            np.where(
                outage,
                np.minimum(95.0, base["cpu_percent"] + ramp * 50),
                np.where(
                    recovery,
                    np.minimum(100.0, 95.0 - rec_frac * (95.0 - base["cpu_percent"])),
                    base["cpu_percent"],
                ),
            ),
        )

        return pd.DataFrame(
            {
                "timestamp": timestamps,
                "throughput_rps": throughput,
                "error_rate": error_rate,
                "p50_latency": p50,
                "p99_latency": p99,
                "cpu_percent": cpu,
                "memory_bytes": np.full(n, base["memory_bytes"]),
            }
        )
