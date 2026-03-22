"""Degradation scenario — deployment regression with visible latency increase."""

from __future__ import annotations

from datetime import datetime, timedelta

from slo_generator.constants import HEALTHY_DEFAULTS, SERVICE_FACTORS
from slo_generator.generator_config import GeneratorConfig
from slo_generator.raw import RawChunk, RawSample, apply_jitter, generate_errors, generate_latencies
from slo_generator.scenarios.base import BaseScenario


class DegradationScenario(BaseScenario):
    """Simulates a bad deployment: latency 5x, error rate 5x, throughput unchanged."""

    name = "degradation"

    def __init__(
        self,
        start: datetime,
        end: datetime,
        *,
        config: GeneratorConfig | None = None,
        event_mode: bool = False,
        ramp_minutes: int = 5,
        latency_multiplier: float = 5.0,
        error_rate_multiplier: float = 5.0,
    ):
        super().__init__(start, end, config=config, event_mode=event_mode)
        if event_mode:
            self.deploy_start = start
        else:
            total = (end - start).total_seconds()
            self.deploy_start = start + timedelta(seconds=total * 0.65)
        self.ramp_end = self.deploy_start + timedelta(minutes=ramp_minutes)
        self.lat_mult = latency_multiplier
        self.err_mult = error_rate_multiplier

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

        deploy_epoch = self.deploy_start.timestamp()
        ramp_end_epoch = self.ramp_end.timestamp()
        ramp_duration = (self.ramp_end - self.deploy_start).total_seconds()

        samples: RawChunk = []
        for ts in timestamps:
            epoch = ts.timestamp()

            if epoch < deploy_epoch:
                # Pre-deployment: normal
                latency_ms = base_latency
                error_rate = base_error_rate
                cpu = base["cpu_percent"]
            elif epoch < ramp_end_epoch:
                # Ramping
                ramp_frac = (epoch - deploy_epoch) / ramp_duration
                latency_ms = base_latency * (1 + ramp_frac * (self.lat_mult - 1))
                error_rate = base_error_rate * (1 + ramp_frac * (self.err_mult - 1))
                cpu = min(100.0, base["cpu_percent"] * (1 + ramp_frac * 0.35))
            else:
                # Post-ramp: sustained degradation
                latency_ms = base_latency * self.lat_mult
                error_rate = base_error_rate * self.err_mult
                cpu = min(100.0, base["cpu_percent"] * 1.35)

            throughput = apply_jitter(base_throughput, jitter, self._rng)
            request_count = round(max(10.0, throughput))
            error_count = generate_errors(request_count, min(error_rate, 1.0), self._rng)
            latencies = generate_latencies(request_count, latency_ms, sigma, self._rng)

            samples.append(
                RawSample(
                    timestamp=ts,
                    service=service,
                    host=host,
                    request_count=request_count,
                    error_count=error_count,
                    latencies_ms=latencies,
                    cpu_percent=min(100.0, max(0.0, apply_jitter(cpu, jitter, self._rng))),
                    memory_bytes=apply_jitter(base["memory_bytes"], jitter, self._rng),
                )
            )
        return samples
