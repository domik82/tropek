"""CLI entry point for the SLO test data generator."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import click
from rich.console import Console

from slo_generator.composer import TimelineComposer
from slo_generator.pipeline import run_pipeline
from slo_generator.scenarios import get_scenario

console = Console()

SCENARIO_NAMES = ["healthy", "outage", "degradation"]
BACKEND_NAMES = ["prometheus", "influxdb", "timescaledb", "csv"]


def _write_metadata(output_dir: Path, config) -> None:
    """Write metadata JSON with timeline info for dashboard generation."""
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        "start": config.start.isoformat(),
        "end": config.end.isoformat(),
        "resolution_seconds": config.resolution_seconds,
        "events": [
            {
                "type": ev.type,
                "start": (config.start + ev.at).isoformat(),
                "end": (config.start + ev.at + ev.duration).isoformat(),
            }
            for ev in config.events
        ],
        "generated_at": datetime.now(tz=UTC).isoformat(),
    }
    metadata_path = output_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2))


def _run_timeline_mode(
    timeline: Path,
    backends: tuple[str, ...],
    output_dir: Path,
    scrape_interval: int,
    influxdb_url: str | None,
    influxdb_token: str | None,
    influxdb_org: str | None,
    influxdb_bucket: str | None,
    timescaledb_dsn: str | None,
    run_promtool: bool,
    prometheus_data_dir: Path | None,
) -> None:
    """Run generation driven by a timeline YAML file."""
    composer = TimelineComposer.from_yaml(timeline)
    config = composer.config

    console.print(f"[bold]Timeline mode: {timeline.name}[/bold]")
    console.print(f"  Time range: {config.start.isoformat()} → {config.end.isoformat()}")
    console.print(f"  Resolution: {config.resolution_seconds}s")
    console.print(f"  Events: {len(config.events)}")

    results = run_pipeline(
        scenario=composer,
        backends=list(backends),
        output_dir=output_dir,
        scenario_name="timeline",
        resolution_seconds=config.resolution_seconds,
        prometheus_scrape_interval=scrape_interval,
        influxdb_url=influxdb_url,
        influxdb_token=influxdb_token,
        influxdb_org=influxdb_org,
        influxdb_bucket=influxdb_bucket,
        timescaledb_dsn=timescaledb_dsn,
        run_promtool=run_promtool,
        prometheus_data_dir=prometheus_data_dir,
    )

    for backend, success in results.items():
        status = "[green]✓[/green]" if success else "[red]✗[/red]"
        console.print(f"  {status} {backend}")

    _write_metadata(output_dir, config)
    console.print(f"\n  Metadata written to {output_dir / 'metadata.json'}")


def _run_scenario_mode(
    scenarios: tuple[str, ...],
    backends: tuple[str, ...],
    hours: int,
    resolution: int,
    output_dir: Path,
    scrape_interval: int,
    influxdb_url: str | None,
    influxdb_token: str | None,
    influxdb_org: str | None,
    influxdb_bucket: str | None,
    timescaledb_dsn: str | None,
    run_promtool: bool,
    prometheus_data_dir: Path | None,
) -> None:
    """Run generation for each named scenario independently."""
    end = datetime.now(tz=UTC)
    start = end - timedelta(hours=hours)

    console.print(f"[bold]Generating {len(scenarios)} scenarios x {len(backends)} backends[/bold]")
    console.print(f"  Time range: {start.isoformat()} → {end.isoformat()}")
    console.print(f"  Resolution: {resolution}s")

    for scenario_name in scenarios:
        console.print(f"\n[bold cyan]Scenario: {scenario_name}[/bold cyan]")
        scenario = get_scenario(scenario_name, start=start, end=end)

        results = run_pipeline(
            scenario=scenario,
            backends=list(backends),
            output_dir=output_dir / scenario_name,
            scenario_name=scenario_name,
            resolution_seconds=resolution,
            prometheus_scrape_interval=scrape_interval,
            influxdb_url=influxdb_url,
            influxdb_token=influxdb_token,
            influxdb_org=influxdb_org,
            influxdb_bucket=influxdb_bucket,
            timescaledb_dsn=timescaledb_dsn,
            run_promtool=run_promtool,
            prometheus_data_dir=prometheus_data_dir,
        )

        for backend, success in results.items():
            status = "[green]✓[/green]" if success else "[red]✗[/red]"
            console.print(f"  {status} {backend}")


@click.command()
@click.option(
    "--scenarios", "-s", multiple=True, default=SCENARIO_NAMES, help="Scenarios to generate"
)
@click.option("--backends", "-b", multiple=True, default=["prometheus"], help="Output backends")
@click.option("--hours", type=int, default=24, help="Duration in hours")
@click.option("--resolution", type=int, default=1, help="Resolution in seconds")
@click.option(
    "--output-dir", type=click.Path(path_type=Path), default=Path("output"), help="Output directory"
)
@click.option("--scrape-interval", type=int, default=30, help="Prometheus scrape interval")
@click.option("--influxdb-url", envvar="INFLUXDB_URL", default=None)
@click.option("--influxdb-token", envvar="INFLUXDB_TOKEN", default=None)
@click.option("--influxdb-org", envvar="INFLUXDB_ORG", default=None)
@click.option("--influxdb-bucket", envvar="INFLUXDB_BUCKET", default=None)
@click.option("--timescaledb-dsn", envvar="TIMESCALEDB_DSN", default=None)
@click.option("--run-promtool/--no-promtool", default=False, help="Run promtool TSDB backfill")
@click.option("--prometheus-data-dir", type=click.Path(path_type=Path), default=None)
@click.option(
    "--timeline",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Timeline YAML file for composed generation",
)
def main(
    scenarios: tuple[str, ...],
    backends: tuple[str, ...],
    hours: int,
    resolution: int,
    output_dir: Path,
    scrape_interval: int,
    influxdb_url: str | None,
    influxdb_token: str | None,
    influxdb_org: str | None,
    influxdb_bucket: str | None,
    timescaledb_dsn: str | None,
    run_promtool: bool,
    prometheus_data_dir: Path | None,
    timeline: Path | None,
) -> None:
    """Generate SLO test data for quality gate evaluation."""
    if timeline is not None:
        _run_timeline_mode(
            timeline=timeline,
            backends=backends,
            output_dir=output_dir,
            scrape_interval=scrape_interval,
            influxdb_url=influxdb_url,
            influxdb_token=influxdb_token,
            influxdb_org=influxdb_org,
            influxdb_bucket=influxdb_bucket,
            timescaledb_dsn=timescaledb_dsn,
            run_promtool=run_promtool,
            prometheus_data_dir=prometheus_data_dir,
        )
    else:
        _run_scenario_mode(
            scenarios=scenarios,
            backends=backends,
            hours=hours,
            resolution=resolution,
            output_dir=output_dir,
            scrape_interval=scrape_interval,
            influxdb_url=influxdb_url,
            influxdb_token=influxdb_token,
            influxdb_org=influxdb_org,
            influxdb_bucket=influxdb_bucket,
            timescaledb_dsn=timescaledb_dsn,
            run_promtool=run_promtool,
            prometheus_data_dir=prometheus_data_dir,
        )

    console.print("\n[bold green]Done![/bold green]")
