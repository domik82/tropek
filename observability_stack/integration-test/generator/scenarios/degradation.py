"""Degradation scenario — deployment regression with visible latency increase."""

from __future__ import annotations

from datetime import datetime, timedelta

from scenarios.base import HEALTHY_PROFILE, BaseScenario, ServiceProfile


class DegradationScenario(BaseScenario):
    """Simulates a bad deployment causing performance degradation.

    Characteristics (matches the brief):
      - Throughput STAYS THE SAME — application still accepts requests
      - P99 latency grows from 80ms → ~400ms (5x)
      - Error rate slightly increases (0.1% → 0.5%)
      - CPU increases modestly (40% → 55%) — code is just slower
      - Memory stays roughly the same

    Timeline:
      [start → deploy_start)     : healthy baseline
      [deploy_start → ramp_end)  : gradual ramp-up of degradation (deployment window)
      [ramp_end → end)           : sustained degraded state — NOT self-healing
    """

    name = "degradation"
    description = (
        "Deployment regression: latency increase, slight error rate rise, throughput unchanged"
    )

    def __init__(
        self,
        start: datetime,
        end: datetime,
        resolution_seconds: int = 30,
        deploy_start: datetime | None = None,
        ramp_minutes: int = 5,
        latency_multiplier: float = 5.0,  # p99 grows by this factor
        error_rate_multiplier: float = 5.0,  # error rate grows by this factor
    ):
        super().__init__(start, end, resolution_seconds)

        total = (end - start).total_seconds()
        if deploy_start is None:
            deploy_start = start + timedelta(seconds=total * 0.65)

        self.deploy_start = deploy_start
        self.ramp_end = deploy_start + timedelta(minutes=ramp_minutes)
        self.latency_multiplier = latency_multiplier
        self.error_rate_multiplier = error_rate_multiplier

    def profile_at(self, t: datetime, service: str, host: str) -> ServiceProfile:
        service_factor = {"frontend": 1.2, "api": 1.0, "backend": 0.8}.get(service, 1.0)
        base_throughput = HEALTHY_PROFILE.throughput_rps * service_factor

        if t < self.deploy_start:
            # Pre-deploy: fully healthy
            return ServiceProfile(
                service=service,
                host=host,
                throughput_rps=base_throughput,
                error_rate=HEALTHY_PROFILE.error_rate,
                p50_latency=HEALTHY_PROFILE.p50_latency,
                p99_latency=HEALTHY_PROFILE.p99_latency,
                cpu_percent=HEALTHY_PROFILE.cpu_percent,
                memory_bytes=HEALTHY_PROFILE.memory_bytes,
            )

        elif t < self.ramp_end:
            # Deployment ramping in — degradation grows linearly
            ramp_total = (self.ramp_end - self.deploy_start).total_seconds()
            ramp_frac = (t - self.deploy_start).total_seconds() / ramp_total  # 0→1

            p99 = HEALTHY_PROFILE.p99_latency * (1 + ramp_frac * (self.latency_multiplier - 1))
            p50 = HEALTHY_PROFILE.p50_latency * (
                1 + ramp_frac * (self.latency_multiplier * 0.5 - 1)
            )
            error_rate = HEALTHY_PROFILE.error_rate * (
                1 + ramp_frac * (self.error_rate_multiplier - 1)
            )
            cpu = HEALTHY_PROFILE.cpu_percent * (
                1 + ramp_frac * 0.35  # up to 35% more CPU
            )

            return ServiceProfile(
                service=service,
                host=host,
                throughput_rps=base_throughput,  # unchanged!
                error_rate=error_rate,
                p50_latency=max(HEALTHY_PROFILE.p50_latency, p50),
                p99_latency=p99,
                cpu_percent=min(100.0, cpu),
                memory_bytes=HEALTHY_PROFILE.memory_bytes,
            )

        else:
            # Sustained degradation — stays bad, no self-healing
            return ServiceProfile(
                service=service,
                host=host,
                throughput_rps=base_throughput,
                error_rate=HEALTHY_PROFILE.error_rate * self.error_rate_multiplier,
                p50_latency=HEALTHY_PROFILE.p50_latency * (self.latency_multiplier * 0.5),
                p99_latency=HEALTHY_PROFILE.p99_latency * self.latency_multiplier,
                cpu_percent=min(100.0, HEALTHY_PROFILE.cpu_percent * 1.35),
                memory_bytes=HEALTHY_PROFILE.memory_bytes,
            )
