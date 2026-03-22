"""Outage scenario — sudden failure affecting all services."""

from __future__ import annotations

from datetime import datetime, timedelta

from slo_generator.constants import HEALTHY_DEFAULTS, SERVICE_FACTORS
from slo_generator.generator_config import GeneratorConfig
from slo_generator.raw import RawChunk, RawSample, apply_jitter, generate_errors, generate_latencies
from slo_generator.scenarios.base import BaseScenario


class OutageScenario(BaseScenario):
    """Simulates a full outage: high errors, low throughput, high latency."""

    name = "outage"

    def __init__(
        self,
        start: datetime,
        end: datetime,
        *,
        config: GeneratorConfig | None = None,
        event_mode: bool = False,
        outage_duration_minutes: int = 30,
        recovery_minutes: int = 10,
    ):
        super().__init__(start, end, config=config, event_mode=event_mode)
        if event_mode:
            self.outage_start = start
            self.outage_end = end - timedelta(minutes=recovery_minutes)
            self.recovery_end = end
        else:
            total = (end - start).total_seconds()
            self.outage_start = start + timedelta(seconds=total * 0.60)
            self.outage_end = self.outage_start + timedelta(minutes=outage_duration_minutes)
            self.recovery_end = self.outage_end + timedelta(minutes=recovery_minutes)

    def _build_raw_samples(
        self,
        timestamps: list[datetime],
        service: str,
        host: str,
    ) -> RawChunk:
        sf = SERVICE_FACTORS.get(service, 1.0)
        base = HEALTHY_DEFAULTS
        base_throughput = base["throughput_rps"] * sf
        base_latency = base["base_latency_ms"]
        jitter = self.config.jitter_pct
        sigma = self.config.latency_sigma
        base_error_rate = self.config.base_error_rate

        outage_start_epoch = self.outage_start.timestamp()
        outage_end_epoch = self.outage_end.timestamp()
        recovery_end_epoch = self.recovery_end.timestamp()
        rec_duration = (self.recovery_end - self.outage_end).total_seconds()

        samples: RawChunk = []
        for ts in timestamps:
            epoch = ts.timestamp()

            if epoch < outage_start_epoch:
                # Pre-outage: normal
                throughput = apply_jitter(base_throughput, jitter, self._rng)
                error_rate = base_error_rate
                latency_ms = base_latency
                cpu = apply_jitter(base["cpu_percent"], jitter, self._rng)
            elif epoch < outage_end_epoch:
                # Outage: ramp over 2 minutes
                ramp = min((epoch - outage_start_epoch) / 120.0, 1.0)
                throughput = max(2.0, base_throughput * (1 - ramp * 0.90))
                error_rate = min(0.95, base_error_rate + ramp * 0.79)
                latency_ms = base_latency * (1 + ramp * 50)  # up to 50x latency
                cpu = min(95.0, base["cpu_percent"] + ramp * 50)
            elif epoch < recovery_end_epoch:
                # Recovery
                rec_frac = min((epoch - outage_end_epoch) / rec_duration, 1.0)
                throughput = max(10.0, 2.0 + rec_frac * (base_throughput - 2.0))
                error_rate = max(base_error_rate, 0.95 - rec_frac * (0.95 - base_error_rate))
                latency_ms = max(base_latency, base_latency * 50 * (1 - rec_frac))
                cpu = max(base["cpu_percent"], 95.0 - rec_frac * (95.0 - base["cpu_percent"]))
            else:
                # Post-recovery: normal
                throughput = apply_jitter(base_throughput, jitter, self._rng)
                error_rate = base_error_rate
                latency_ms = base_latency
                cpu = apply_jitter(base["cpu_percent"], jitter, self._rng)

            request_count = round(max(1.0, throughput))
            error_count = generate_errors(request_count, error_rate, self._rng)
            latencies = generate_latencies(request_count, latency_ms, sigma, self._rng)

            samples.append(
                RawSample(
                    timestamp=ts,
                    service=service,
                    host=host,
                    request_count=request_count,
                    error_count=error_count,
                    latencies_ms=latencies,
                    cpu_percent=min(100.0, max(0.0, cpu)),
                    memory_bytes=apply_jitter(base["memory_bytes"], jitter, self._rng),
                )
            )
        return samples
