"""Adapter factory."""

from __future__ import annotations

from typing import Any

from slo_generator.adapters.base import BaseAdapter


def get_adapter(backend: str, **config: Any) -> BaseAdapter:
    """Factory for creating adapters by backend name."""
    from slo_generator.adapters.csv import CSVAdapter
    from slo_generator.adapters.influxdb import InfluxDBAdapter
    from slo_generator.adapters.prometheus import PrometheusAdapter
    from slo_generator.adapters.timescaledb import TimescaleDBAdapter

    adapters: dict[str, type[BaseAdapter]] = {
        "prometheus": PrometheusAdapter,
        "influxdb": InfluxDBAdapter,
        "timescaledb": TimescaleDBAdapter,
        "csv": CSVAdapter,
    }
    if backend not in adapters:
        raise ValueError(f"unknown backend: {backend!r}, expected one of {list(adapters)}")
    return adapters[backend](**config)
