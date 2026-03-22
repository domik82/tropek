"""Step change scenario — sustained level shift after config change or capacity reduction."""

from __future__ import annotations

from datetime import datetime, timedelta

from slo_generator.constants import HEALTHY_DEFAULTS, HOST_FACTORS, SERVICE_FACTORS
from slo_generator.generator_config import GeneratorConfig
from slo_generator.raw import RawChunk, RawSample, apply_jitter, generate_errors, generate_latencies
from slo_generator.scenarios.base import BaseScenario


class StepChangeScenario(BaseScenario):
    """Simulates a sustained level shift with brief ramp to new baseline."""

    name = "step_change"

    def __init__(
        self,
        start: datetime,
        end: datetime,
        *,
        config: GeneratorConfig | None = None,
        event_mode: bool = True,
        latency_multiplier: float = 1.5,
        throughput_multiplier: float = 1.0,
        error_rate_multiplier: float = 1.0,
        ramp_minutes: int = 2,
    ):
        super().__init__(start, end, config=config, event_mode=event_mode)
        self.lat_mult = latency_multiplier
        self.tput_mult = throughput_multiplier
        self.err_mult = error_rate_multiplier
        self.ramp_end = start + timedelta(minutes=ramp_minutes)

    def _build_raw_samples(
        self,
        timestamps: list[datetime],
        service: str,
        host: str,
    ) -> RawChunk:
        sf = SERVICE_FACTORS.get(service, 1.0)
        hf = HOST_FACTORS.get(host, 1.0)
        base = HEALTHY_DEFAULTS
        base_throughput = base["throughput_rps"] * sf * hf
        base_latency = base["base_latency_ms"]
        jitter = self.config.jitter_pct
        sigma = self.config.latency_sigma
        base_error_rate = self.config.base_error_rate

        start_epoch = self.start.timestamp()
        ramp_end_epoch = self.ramp_end.timestamp()
        ramp_duration = max((self.ramp_end - self.start).total_seconds(), 1.0)

        samples: RawChunk = []
        for ts in timestamps:
            epoch = ts.timestamp()

            if epoch < ramp_end_epoch:
                ramp_frac = (epoch - start_epoch) / ramp_duration
                throughput = base_throughput + ramp_frac * (
                    base_throughput * self.tput_mult - base_throughput
                )
                latency_ms = base_latency + ramp_frac * (
                    base_latency * self.lat_mult - base_latency
                )
                error_rate = base_error_rate + ramp_frac * (
                    base_error_rate * self.err_mult - base_error_rate
                )
                cpu = base["cpu_percent"] + ramp_frac * (
                    base["cpu_percent"] * self.lat_mult * 0.8 - base["cpu_percent"]
                )
            else:
                throughput = base_throughput * self.tput_mult
                latency_ms = base_latency * self.lat_mult
                error_rate = base_error_rate * self.err_mult
                cpu = base["cpu_percent"] * self.lat_mult * 0.8

            throughput = apply_jitter(max(10.0, throughput), jitter, self._rng)
            request_count = round(throughput)
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
                    memory_bytes=apply_jitter(base["memory_bytes"] * hf, jitter, self._rng),
                )
            )
        return samples
