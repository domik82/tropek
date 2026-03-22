"""Polska scenario — easter egg using Poland's geographic contour as metric envelope."""

from __future__ import annotations

from datetime import datetime

import numpy as np

from slo_generator.constants import HEALTHY_DEFAULTS, HOST_FACTORS, SERVICE_FACTORS
from slo_generator.generator_config import GeneratorConfig
from slo_generator.raw import RawChunk, RawSample, apply_jitter, generate_errors, generate_latencies
from slo_generator.scenarios.base import BaseScenario
from slo_generator.scenarios.polska_contour import POLSKA_LOWER, POLSKA_UPPER, POLSKA_X


class PolskaScenario(BaseScenario):
    """Generates metrics shaped like Poland's geographic contour."""

    name = "polska"

    def __init__(
        self,
        start: datetime,
        end: datetime,
        *,
        config: GeneratorConfig | None = None,
        event_mode: bool = True,
        noise_amplitude: float = 0.05,
        throughput_range: tuple[float, float] = (50.0, 200.0),
        latency_range_ms: tuple[float, float] = (10.0, 500.0),
    ):
        super().__init__(start, end, config=config, event_mode=event_mode)
        self.noise_amplitude = noise_amplitude
        self.throughput_range = throughput_range
        self.latency_range_ms = latency_range_ms

    def _build_raw_samples(
        self,
        timestamps: list[datetime],
        service: str,
        host: str,
    ) -> RawChunk:
        sf = SERVICE_FACTORS.get(service, 1.0)
        hf = HOST_FACTORS.get(host, 1.0)
        base = HEALTHY_DEFAULTS
        jitter = self.config.jitter_pct
        sigma = self.config.latency_sigma

        total_seconds = (self.end - self.start).total_seconds()
        start_epoch = self.start.timestamp()

        samples: RawChunk = []
        for ts in timestamps:
            epoch = ts.timestamp()
            progress = min(max((epoch - start_epoch) / total_seconds, 0.0), 1.0)

            # Interpolate contour values
            upper = float(np.interp(progress, POLSKA_X, POLSKA_UPPER))
            lower = float(np.interp(progress, POLSKA_X, POLSKA_LOWER))

            # Add noise
            noise_t = self._rng.normal(0, self.noise_amplitude)
            noise_l = self._rng.normal(0, self.noise_amplitude)

            # Map upper contour -> throughput
            tmin, tmax = self.throughput_range
            throughput = max(
                10.0, min(tmax * 2, tmin + (upper + noise_t) * (tmax - tmin) * sf * hf)
            )

            # Map lower contour -> latency (inverted: lower contour = higher latency)
            lmin, lmax = self.latency_range_ms
            latency_ms = max(lmin, min(lmax * 2, lmin + (1.0 - lower + noise_l) * (lmax - lmin)))

            throughput = apply_jitter(throughput, jitter, self._rng)
            request_count = round(throughput)
            error_count = generate_errors(request_count, self.config.base_error_rate, self._rng)
            latencies = generate_latencies(request_count, latency_ms, sigma, self._rng)

            cpu = min(100.0, max(0.0, 30 + upper * 40))

            samples.append(
                RawSample(
                    timestamp=ts,
                    service=service,
                    host=host,
                    request_count=request_count,
                    error_count=error_count,
                    latencies_ms=latencies,
                    cpu_percent=cpu,
                    memory_bytes=apply_jitter(base["memory_bytes"] * hf, jitter, self._rng),
                )
            )
        return samples
