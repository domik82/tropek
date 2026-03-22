"""Shaper factory."""

from __future__ import annotations

from typing import Any

from slo_generator.shapers.base import BaseShaper


def get_shaper(backend: str, **config: Any) -> BaseShaper:
    """Factory for creating shapers by backend name."""
    from slo_generator.shapers.influxdb import InfluxDBShaper
    from slo_generator.shapers.prometheus import PrometheusShaper
    from slo_generator.shapers.raw import RawShaper
    from slo_generator.shapers.timescaledb import TimescaleDBShaper

    shapers: dict[str, type[BaseShaper]] = {
        "prometheus": PrometheusShaper,
        "influxdb": InfluxDBShaper,
        "timescaledb": TimescaleDBShaper,
        "csv": RawShaper,
    }
    if backend not in shapers:
        raise ValueError(f"unknown backend: {backend!r}, expected one of {list(shapers)}")
    return shapers[backend](**config)
