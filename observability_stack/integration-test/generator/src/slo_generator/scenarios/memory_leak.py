"""Memory leak scenario — exponential latency growth over days/weeks until crash."""

from __future__ import annotations

import math
from datetime import datetime

from slo_generator.constants import HEALTHY_DEFAULTS, HOST_FACTORS, SERVICE_FACTORS
from slo_generator.generator_config import GeneratorConfig
from slo_generator.raw import RawChunk, RawSample, apply_jitter, generate_errors, generate_latencies
from slo_generator.scenarios.base import BaseScenario


class MemoryLeakScenario(BaseScenario):
    """Simulates a slow memory leak causing exponential latency degradation."""

    name = "memory_leak"

    def __init__(
        self,
        start: datetime,
        end: datetime,
        *,
        config: GeneratorConfig | None = None,
        event_mode: bool = True,
        growth_rate: float = 0.003,
        crash_at_end: bool = True,
    ):
        super().__init__(start, end, config=config, event_mode=event_mode)
        self.growth_rate = growth_rate
        self.crash_at_end = crash_at_end

    def _build_raw_samples(
        self,
        timestamps: list[datetime],
        service: str,
        host: str,
    ) -> RawChunk:
        sf = SERVICE_FACTORS.get(service, 1.0)
        hf = HOST_FACTORS.get(host, 1.0)
        base = HEALTHY_DEFAULTS
        base_latency = base["base_latency_ms"]
        jitter = self.config.jitter_pct
        sigma = self.config.latency_sigma

        total_seconds = (self.end - self.start).total_seconds()
        start_epoch = self.start.timestamp()

        max_memory = 2 * 1024 * 1024 * 1024 * 0.95
        base_mem = base["memory_bytes"] * hf
        crash_threshold = 1.0 - (3600 / total_seconds) if self.crash_at_end else 2.0

        samples: RawChunk = []
        for ts in timestamps:
            epoch = ts.timestamp()
            progress = min(max((epoch - start_epoch) / total_seconds, 0.0), 1.0)

            # Exponential growth
            growth = math.exp(self.growth_rate * 100.0 * progress)

            # Memory grows linearly toward 95% of 2GB
            memory = base_mem + progress * (max_memory - base_mem)

            # Throughput decreases with GC pressure
            throughput = max(10.0, base["throughput_rps"] * sf * hf * (1.0 - 0.3 * progress))

            # Latency grows exponentially
            latency_ms = base_latency * sf * growth

            # Error rate stays low until 80% through
            if progress < 0.8:
                error_rate = self.config.base_error_rate
            else:
                error_rate = self.config.base_error_rate + (progress - 0.8) * 0.5

            # CPU increases with memory pressure
            cpu = min(100.0, base["cpu_percent"] + progress * 30)

            # Crash phase: final hour
            if self.crash_at_end and progress >= crash_threshold:
                crash_progress = min((progress - crash_threshold) / (1.0 - crash_threshold), 1.0)
                throughput = max(0.1, 10 * (1 - crash_progress))
                error_rate = min(1.0, 0.5 + 0.5 * crash_progress)
                latency_ms = base_latency * 150  # timeout-level
                cpu = 99.0

            throughput = apply_jitter(throughput, jitter, self._rng)
            request_count = round(max(1.0, throughput))
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
                    cpu_percent=min(100.0, max(0.0, cpu)),
                    memory_bytes=apply_jitter(memory, jitter, self._rng),
                )
            )
        return samples
