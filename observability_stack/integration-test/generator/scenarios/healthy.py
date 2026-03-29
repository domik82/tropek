"""Healthy scenario — everything is normal, mild diurnal variation."""

from __future__ import annotations

import math
from datetime import datetime

from scenarios.base import HEALTHY_PROFILE, BaseScenario, ServiceProfile


class HealthyScenario(BaseScenario):
    """Simulates a healthy system over a configurable time range.

    Adds mild diurnal variation (~±15% throughput/CPU over 24h cycle)
    to make the graphs look realistic rather than flat lines.
    """

    name = "healthy"
    description = "Flat baseline — all metrics within normal bounds"

    def profile_at(self, t: datetime, service: str, host: str) -> ServiceProfile:
        # Diurnal cycle: peak at 14:00, trough at 03:00
        hour_fraction = (t.hour + t.minute / 60) / 24
        diurnal = 1.0 + 0.15 * math.sin(2 * math.pi * (hour_fraction - 0.25))

        # Slight per-service variation so graphs are distinguishable
        service_factor = {"frontend": 1.2, "api": 1.0, "backend": 0.8}.get(service, 1.0)
        host_factor = {"host1": 1.05, "host2": 0.95}.get(host, 1.0)

        throughput = HEALTHY_PROFILE.throughput_rps * diurnal * service_factor * host_factor
        cpu = HEALTHY_PROFILE.cpu_percent * (
            0.8 + 0.4 * (throughput / (HEALTHY_PROFILE.throughput_rps * service_factor))
        )

        return ServiceProfile(
            service=service,
            host=host,
            throughput_rps=max(10.0, throughput),
            error_rate=HEALTHY_PROFILE.error_rate,
            p50_latency=HEALTHY_PROFILE.p50_latency,
            p99_latency=HEALTHY_PROFILE.p99_latency,
            cpu_percent=min(100.0, cpu),
            memory_bytes=HEALTHY_PROFILE.memory_bytes * host_factor,
        )
