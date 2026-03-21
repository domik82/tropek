"""Pipeline wiring: scenario → shaper → adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.console import Console

from slo_generator.adapters import get_adapter
from slo_generator.adapters.base import BaseAdapter
from slo_generator.shapers import get_shaper
from slo_generator.shapers.base import BaseShaper

console = Console()

_Pair = tuple[str, BaseShaper, BaseAdapter]


def _build_kwargs(
    backend: str,
    output_dir: Path,
    scenario_name: str,
    prometheus_scrape_interval: int,
    influxdb_url: str | None,
    influxdb_token: str | None,
    influxdb_org: str | None,
    influxdb_bucket: str | None,
    timescaledb_dsn: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (shaper_kwargs, adapter_kwargs) for the given backend."""
    shaper_kwargs: dict[str, Any] = {}
    adapter_kwargs: dict[str, Any] = {}

    if backend == "prometheus":
        shaper_kwargs["scrape_interval"] = prometheus_scrape_interval
        adapter_kwargs["output_path"] = output_dir / f"{scenario_name}_metrics.om"
    elif backend == "influxdb":
        adapter_kwargs.update(
            url=influxdb_url,
            token=influxdb_token,
            org=influxdb_org,
            bucket=influxdb_bucket,
        )
    elif backend == "timescaledb":
        adapter_kwargs["dsn"] = timescaledb_dsn
    elif backend == "csv":
        adapter_kwargs["output_path"] = output_dir / f"{scenario_name}.csv"

    return shaper_kwargs, adapter_kwargs


def _build_pairs(
    backends: list[str],
    output_dir: Path,
    scenario_name: str,
    prometheus_scrape_interval: int,
    influxdb_url: str | None,
    influxdb_token: str | None,
    influxdb_org: str | None,
    influxdb_bucket: str | None,
    timescaledb_dsn: str | None,
    results: dict[str, bool],
) -> list[_Pair]:
    """Instantiate (backend, shaper, adapter) triples; mark failures in results."""
    pairs: list[_Pair] = []
    for backend in backends:
        try:
            shaper_kwargs, adapter_kwargs = _build_kwargs(
                backend,
                output_dir,
                scenario_name,
                prometheus_scrape_interval,
                influxdb_url,
                influxdb_token,
                influxdb_org,
                influxdb_bucket,
                timescaledb_dsn,
            )
            shaper = get_shaper(backend, **shaper_kwargs)
            adapter = get_adapter(backend, **adapter_kwargs)
            pairs.append((backend, shaper, adapter))
        except Exception as exc:
            console.print(f"[yellow]Skipping {backend}: {exc}[/yellow]")
            results[backend] = False
    return pairs


def _stream_and_finalize(
    scenario: Any,
    pairs: list[_Pair],
    resolution_seconds: int,
    results: dict[str, bool],
) -> None:
    """Stream all chunks through shapers/adapters, then finalize each adapter."""
    for chunk in scenario.generate(resolution_seconds=resolution_seconds):
        for backend, shaper, adapter in pairs:
            try:
                for shaped in shaper.shape(chunk):
                    adapter.write_chunk(shaped)
            except Exception as exc:
                console.print(f"[red]{backend} write failed: {exc}[/red]")
                results[backend] = False

    for backend, shaper, adapter in pairs:
        try:
            for shaped in shaper.finalize():
                adapter.write_chunk(shaped)
            adapter.close()
            if backend not in results:
                results[backend] = True
            console.print(f"[green]{backend}: done[/green]")
        except Exception as exc:
            console.print(f"[red]{backend} finalize failed: {exc}[/red]")
            results[backend] = False


def run_pipeline(
    scenario: Any,
    backends: list[str],
    output_dir: Path,
    scenario_name: str,
    resolution_seconds: int = 1,
    prometheus_scrape_interval: int = 30,
    influxdb_url: str | None = None,
    influxdb_token: str | None = None,
    influxdb_org: str | None = None,
    influxdb_bucket: str | None = None,
    timescaledb_dsn: str | None = None,
    run_promtool: bool = False,
    prometheus_data_dir: Path | None = None,
) -> dict[str, bool]:
    """Run the generation pipeline for one scenario across all requested backends.

    Returns a dict of backend -> success (True/False).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, bool] = {}

    pairs = _build_pairs(
        backends,
        output_dir,
        scenario_name,
        prometheus_scrape_interval,
        influxdb_url,
        influxdb_token,
        influxdb_org,
        influxdb_bucket,
        timescaledb_dsn,
        results,
    )
    _stream_and_finalize(scenario, pairs, resolution_seconds, results)

    if run_promtool and results.get("prometheus") and prometheus_data_dir:
        from slo_generator.adapters.prometheus import PrometheusAdapter

        om_path = output_dir / f"{scenario_name}_metrics.om"
        PrometheusAdapter.run_promtool(om_path, prometheus_data_dir)

    return results
