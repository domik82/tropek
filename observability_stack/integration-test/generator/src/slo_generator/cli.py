"""CLI entry point for the SLO test data generator."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import click
from rich.console import Console

from slo_generator.pipeline import run_pipeline
from slo_generator.scenarios import get_scenario

console = Console()

SCENARIO_NAMES = ["healthy", "outage", "degradation"]
BACKEND_NAMES = ["prometheus", "influxdb", "timescaledb", "csv"]


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
) -> None:
    """Generate SLO test data for quality gate evaluation."""
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

    console.print("\n[bold green]Done![/bold green]")
