"""Shared constants for the SLO test data generator."""

from __future__ import annotations

SERVICES: list[str] = ["frontend", "api", "backend"]
HOSTS: list[str] = ["host1", "host2"]

# Standard Prometheus histogram buckets for request durations (seconds)
DURATION_BUCKETS: list[float] = [
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
]

# Profile DataFrame columns — every scenario must produce exactly these
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
    "error_rate": 0.001,
    "p50_latency": 0.020,
    "p99_latency": 0.080,
    "cpu_percent": 40.0,
    "memory_bytes": 512 * 1024 * 1024,
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
