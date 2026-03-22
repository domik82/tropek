"""Traffic spike scenario — sudden burst causing 429 or 5xx errors."""

from __future__ import annotations

from datetime import datetime

from slo_generator.constants import HEALTHY_DEFAULTS, HOST_FACTORS, SERVICE_FACTORS
from slo_generator.generator_config import GeneratorConfig
from slo_generator.raw import RawChunk, RawSample, apply_jitter, generate_errors, generate_latencies
from slo_generator.scenarios.base import BaseScenario


class TrafficSpikeScenario(BaseScenario):
    """Simulates a sudden traffic burst with rate-limit or overload behavior."""

    name = "traffic_spike"

    def __init__(
        self,
        start: datetime,
        end: datetime,
        *,
        config: GeneratorConfig | None = None,
        event_mode: bool = True,
        spike_multiplier: float = 5.0,
        error_mode: str = "rate_limit",
        ramp_minutes: int = 5,
        sustain_fraction: float = 0.6,
    ):
        super().__init__(start, end, config=config, event_mode=event_mode)
        self.spike_multiplier = spike_multiplier
        self.error_mode = error_mode
        self.ramp_minutes = ramp_minutes
        self.sustain_fraction = sustain_fraction

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

        total_seconds = (self.end - self.start).total_seconds()
        start_epoch = self.start.timestamp()
        ramp_frac = self.ramp_minutes * 60 / total_seconds
        sustain_end = ramp_frac + self.sustain_fraction
        capacity = base_throughput * 2.0

        samples: RawChunk = []
        for ts in timestamps:
            epoch = ts.timestamp()
            progress = min(max((epoch - start_epoch) / total_seconds, 0.0), 1.0)

            # Traffic envelope: ramp -> sustain -> taper
            if progress < ramp_frac:
                envelope = 1.0 + (self.spike_multiplier - 1.0) * (progress / ramp_frac)
            elif progress < sustain_end:
                envelope = self.spike_multiplier
            elif progress < 1.0:
                envelope = self.spike_multiplier * (
                    1.0 - (progress - sustain_end) / (1.0 - sustain_end)
                )
            else:
                envelope = 1.0

            incoming = base_throughput * envelope

            if self.error_mode == "rate_limit":
                throughput = incoming
                excess = max(0.0, incoming - capacity)
                error_rate = min(excess / max(incoming, 1.0), 0.9)
                latency_ms = base_latency * (1.0 + 0.2 * (envelope - 1.0))
                cpu = min(95.0, base["cpu_percent"] * min(envelope, 2.0))
            else:  # overload
                served = incoming if incoming <= capacity else capacity * (capacity / incoming)
                throughput = served
                excess = max(0.0, incoming - capacity)
                error_rate = min(0.5 * excess / max(incoming, 1.0), 0.95)
                queue_factor = max(1.0, envelope**2)
                latency_ms = base_latency * queue_factor
                cpu = min(100.0, base["cpu_percent"] * min(envelope, 2.5))

            throughput = apply_jitter(throughput, jitter, self._rng)
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
                    memory_bytes=apply_jitter(base["memory_bytes"] * hf, jitter, self._rng),
                )
            )
        return samples
