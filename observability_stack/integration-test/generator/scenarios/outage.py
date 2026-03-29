"""Outage scenario — sudden failure affecting all services."""

from __future__ import annotations

from datetime import datetime, timedelta

from scenarios.base import HEALTHY_PROFILE, BaseScenario, ServiceProfile


class OutageScenario(BaseScenario):
    """Simulates a full outage event.

    Timeline:
      [start → outage_start)  : healthy baseline
      [outage_start → outage_end) : outage — high errors, low throughput, high latency
      [outage_end → end)      : recovery (gradual return to normal over recovery_minutes)

    Outage characteristics:
      - Throughput drops to ~10% of normal (requests failing/timing out)
      - Error rate jumps to ~80%
      - P99 latency spikes to 5–10 seconds
      - CPU spikes (threads blocked waiting)
      - Memory stays roughly same (not a memory leak)
    """

    name = "outage"
    description = "Sudden outage: high error rate, latency spike, throughput collapse"

    def __init__(
        self,
        start: datetime,
        end: datetime,
        resolution_seconds: int = 30,
        outage_start: datetime | None = None,
        outage_duration_minutes: int = 30,
        recovery_minutes: int = 10,
    ):
        super().__init__(start, end, resolution_seconds)

        # Default: outage starts at 60% through the total window
        total = (end - start).total_seconds()
        if outage_start is None:
            outage_start = start + timedelta(seconds=total * 0.60)

        self.outage_start = outage_start
        self.outage_end = outage_start + timedelta(minutes=outage_duration_minutes)
        self.recovery_end = self.outage_end + timedelta(minutes=recovery_minutes)

    def profile_at(self, t: datetime, service: str, host: str) -> ServiceProfile:
        service_factor = {"frontend": 1.2, "api": 1.0, "backend": 0.8}.get(service, 1.0)

        if t < self.outage_start:
            # Pre-outage: healthy
            return ServiceProfile(
                service=service,
                host=host,
                throughput_rps=HEALTHY_PROFILE.throughput_rps * service_factor,
                error_rate=HEALTHY_PROFILE.error_rate,
                p50_latency=HEALTHY_PROFILE.p50_latency,
                p99_latency=HEALTHY_PROFILE.p99_latency,
                cpu_percent=HEALTHY_PROFILE.cpu_percent,
                memory_bytes=HEALTHY_PROFILE.memory_bytes,
            )

        elif t < self.outage_end:
            # Outage active
            # Ramp into outage over first 2 minutes for realism
            ramp_secs = 120
            elapsed = (t - self.outage_start).total_seconds()
            ramp = min(1.0, elapsed / ramp_secs)

            throughput = HEALTHY_PROFILE.throughput_rps * service_factor * (1 - ramp * 0.90)
            error_rate = HEALTHY_PROFILE.error_rate + ramp * 0.79  # up to 80%
            p99 = HEALTHY_PROFILE.p99_latency + ramp * 9.92  # up to ~10s

            return ServiceProfile(
                service=service,
                host=host,
                throughput_rps=max(2.0, throughput),
                error_rate=min(0.95, error_rate),
                p50_latency=HEALTHY_PROFILE.p50_latency * (1 + ramp * 5),
                p99_latency=p99,
                cpu_percent=min(95.0, HEALTHY_PROFILE.cpu_percent + ramp * 50),
                memory_bytes=HEALTHY_PROFILE.memory_bytes,
            )

        elif t < self.recovery_end:
            # Recovery: linear interpolation back to healthy
            total_recovery = (self.recovery_end - self.outage_end).total_seconds()
            elapsed = (t - self.outage_end).total_seconds()
            recovery_frac = elapsed / total_recovery  # 0.0 → 1.0

            throughput = 2.0 + recovery_frac * (
                HEALTHY_PROFILE.throughput_rps * service_factor - 2.0
            )
            error_rate = 0.95 - recovery_frac * (0.95 - HEALTHY_PROFILE.error_rate)
            p99 = 10.0 - recovery_frac * (10.0 - HEALTHY_PROFILE.p99_latency)
            cpu = 95.0 - recovery_frac * (95.0 - HEALTHY_PROFILE.cpu_percent)

            return ServiceProfile(
                service=service,
                host=host,
                throughput_rps=max(10.0, throughput),
                error_rate=max(HEALTHY_PROFILE.error_rate, error_rate),
                p50_latency=max(
                    HEALTHY_PROFILE.p50_latency,
                    HEALTHY_PROFILE.p50_latency * (1 + (1 - recovery_frac) * 5),
                ),
                p99_latency=max(HEALTHY_PROFILE.p99_latency, p99),
                cpu_percent=min(100.0, cpu),
                memory_bytes=HEALTHY_PROFILE.memory_bytes,
            )

        else:
            # Post-recovery: back to healthy
            return ServiceProfile(
                service=service,
                host=host,
                throughput_rps=HEALTHY_PROFILE.throughput_rps * service_factor,
                error_rate=HEALTHY_PROFILE.error_rate,
                p50_latency=HEALTHY_PROFILE.p50_latency,
                p99_latency=HEALTHY_PROFILE.p99_latency,
                cpu_percent=HEALTHY_PROFILE.cpu_percent,
                memory_bytes=HEALTHY_PROFILE.memory_bytes,
            )
