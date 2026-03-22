"""Shared constants for the SLO test data generator."""

from __future__ import annotations

from slo_generator.generator_config import MICROMETER_BUCKETS_MS

SERVICES: list[str] = ["frontend", "api", "backend"]
HOSTS: list[str] = ["host1", "host2"]

# Micrometer histogram buckets in seconds (for Prometheus OpenMetrics output)
MICROMETER_BUCKETS_SECONDS: list[float] = [b / 1000.0 for b in MICROMETER_BUCKETS_MS]

# Legacy: kept until all consumers are migrated to GeneratorConfig
DURATION_BUCKETS: list[float] = MICROMETER_BUCKETS_SECONDS

# Legacy: kept until scenarios are refactored to produce RawSample
PROFILE_COLUMNS: list[str] = [
    "timestamp",
    "service",
    "host",
    "throughput_rps",
    "error_rate",
    "p50_latency",
    "p99_latency",
    "cpu_percent",
    "memory_bytes",
]

# Healthy baseline values (used as defaults across scenarios)
HEALTHY_DEFAULTS: dict[str, float] = {
    "throughput_rps": 100.0,
    "base_latency_ms": 20.0,
    "cpu_percent": 40.0,
    "memory_bytes": 512 * 1024 * 1024,
    # Legacy keys — kept until scenarios are refactored
    "error_rate": 0.001,
    "p50_latency": 0.020,
    "p99_latency": 0.080,
}

# Per-service throughput scaling factors
SERVICE_FACTORS: dict[str, float] = {
    "frontend": 1.2,
    "api": 1.0,
    "backend": 0.8,
}

# Per-host scaling factors
HOST_FACTORS: dict[str, float] = {
    "host1": 1.05,
    "host2": 0.95,
}
