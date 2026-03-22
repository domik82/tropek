"""Healthy scenario — everything is normal, mild diurnal variation."""

from __future__ import annotations

import math
from datetime import datetime

from slo_generator.constants import HEALTHY_DEFAULTS, HOST_FACTORS, SERVICE_FACTORS
from slo_generator.raw import RawChunk, RawSample, apply_jitter, generate_errors, generate_latencies
from slo_generator.scenarios.base import BaseScenario


class HealthyScenario(BaseScenario):
    """Simulates a healthy system with mild diurnal variation (~±15%)."""

    name = "healthy"

    def _build_raw_samples(
        self,
        timestamps: list[datetime],
        service: str,
        host: str,
    ) -> RawChunk:
        sf = SERVICE_FACTORS.get(service, 1.0)
        hf = HOST_FACTORS.get(host, 1.0)

        base_throughput = HEALTHY_DEFAULTS["throughput_rps"] * sf * hf
        base_latency = HEALTHY_DEFAULTS["base_latency_ms"]
        base_cpu = HEALTHY_DEFAULTS["cpu_percent"]
        base_memory = HEALTHY_DEFAULTS["memory_bytes"] * hf
        jitter = self.config.jitter_pct
        sigma = self.config.latency_sigma
        error_rate = self.config.base_error_rate

        samples: RawChunk = []
        for ts in timestamps:
            hour_frac = ts.hour + ts.minute / 60.0
            diurnal = 1.0 + 0.15 * math.sin(2 * math.pi * (hour_frac / 24.0 - 0.25))

            throughput = max(10.0, apply_jitter(base_throughput * diurnal, jitter, self._rng))
            request_count = round(throughput)

            latency_ms = base_latency * diurnal
            latencies = generate_latencies(request_count, latency_ms, sigma, self._rng)

            error_count = generate_errors(request_count, error_rate, self._rng)

            cpu = min(
                100.0,
                max(
                    0.0,
                    apply_jitter(
                        base_cpu * (0.8 + 0.4 * (throughput / (base_throughput))),
                        jitter,
                        self._rng,
                    ),
                ),
            )
            memory = apply_jitter(base_memory, jitter, self._rng)

            samples.append(
                RawSample(
                    timestamp=ts,
                    service=service,
                    host=host,
                    request_count=request_count,
                    error_count=error_count,
                    latencies_ms=latencies,
                    cpu_percent=cpu,
                    memory_bytes=memory,
                )
            )
        return samples
