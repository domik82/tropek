"""Traffic spike scenario — sudden burst causing 429 or 5xx errors."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from slo_generator.constants import HEALTHY_DEFAULTS, HOST_FACTORS, SERVICE_FACTORS
from slo_generator.scenarios.base import BaseScenario


class TrafficSpikeScenario(BaseScenario):
    """Simulates a sudden traffic burst with rate-limit or overload behavior."""

    name = "traffic_spike"

    def __init__(
        self,
        start: datetime,
        end: datetime,
        *,
        event_mode: bool = True,
        spike_multiplier: float = 5.0,
        error_mode: str = "rate_limit",
        ramp_minutes: int = 5,
        sustain_fraction: float = 0.6,
    ):
        super().__init__(start, end, event_mode=event_mode)
        self.spike_multiplier = spike_multiplier
        self.error_mode = error_mode
        self.ramp_minutes = ramp_minutes
        self.sustain_fraction = sustain_fraction

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
        base_throughput = base["throughput_rps"] * sf * hf

        total_seconds = (self.end - self.start).total_seconds()
        ts_epoch = timestamps.astype(np.int64) / 1e9
        start_epoch = self.start.timestamp()
        progress = np.clip((ts_epoch - start_epoch) / total_seconds, 0.0, 1.0)

        ramp_frac = self.ramp_minutes * 60 / total_seconds
        sustain_end = ramp_frac + self.sustain_fraction
        taper_end = 1.0

        # Traffic envelope: ramp -> sustain -> taper
        envelope = np.where(
            progress < ramp_frac,
            1.0 + (self.spike_multiplier - 1.0) * (progress / ramp_frac),
            np.where(
                progress < sustain_end,
                self.spike_multiplier,
                np.where(
                    progress < taper_end,
                    self.spike_multiplier
                    * (1.0 - (progress - sustain_end) / (taper_end - sustain_end)),
                    1.0,
                ),
            ),
        )

        incoming_traffic = base_throughput * envelope
        capacity = base_throughput * 2.0  # system handles ~2x baseline

        if self.error_mode == "rate_limit":
            throughput = incoming_traffic  # total requests (including 429s)
            excess = np.maximum(0.0, incoming_traffic - capacity)
            error_rate = np.clip(excess / np.maximum(incoming_traffic, 1.0), 0.0, 0.9)
            p50 = np.full(n, base["p50_latency"])
            p99 = np.full(n, base["p99_latency"]) * (1.0 + 0.2 * (envelope - 1.0))
            cpu = np.clip(base["cpu_percent"] * np.minimum(envelope, 2.0), 0.0, 95.0)
        else:  # overload
            # System saturates: throughput collapses above capacity
            served = np.where(
                incoming_traffic <= capacity,
                incoming_traffic,
                capacity * (capacity / incoming_traffic),
            )
            throughput = served
            excess = np.maximum(0.0, incoming_traffic - capacity)
            error_rate = np.clip(0.5 * excess / np.maximum(incoming_traffic, 1.0), 0.0, 0.95)
            # Latency spikes with queue depth
            queue_factor = np.maximum(1.0, envelope**2)
            p50 = base["p50_latency"] * queue_factor
            p99 = base["p99_latency"] * queue_factor * 2.0
            cpu = np.clip(base["cpu_percent"] * np.minimum(envelope, 2.5), 0.0, 100.0)

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
