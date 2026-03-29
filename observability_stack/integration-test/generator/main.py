"""SLO Test Data Generator — main CLI entry point.

Usage examples:

  # Generate all scenarios, push to Prometheus + InfluxDB + CSV
  python main.py --scenario all --days 7 --resolution 30

  # Generate only outage scenario with 1h outage duration
  python main.py --scenario outage --outage-duration 60

  # Dry run: write CSVs only, skip remote backends
  python main.py --scenario all --csv-only --output-dir ./output

  # Custom Prometheus output path (for promtool backfill)
  python main.py --scenario all --prometheus-output /data/metrics.om
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import click
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from scenarios import DegradationScenario, HealthyScenario, OutageScenario

from adapters import CSVAdapter, InfluxDBAdapter, PrometheusAdapter

console = Console()


def now_utc() -> datetime:
    return datetime.now(tz=UTC)


def run_promtool_backfill(om_file: Path, tsdb_dir: Path) -> bool:
    """Run promtool to convert OpenMetrics file into Prometheus TSDB blocks.
    Returns True on success.
    """
    cmd = ["promtool", "tsdb", "create-blocks-from", "openmetrics", str(om_file), str(tsdb_dir)]
    console.print(f"[cyan]Running:[/cyan] {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        console.print(f"[red]promtool failed:[/red]\n{result.stderr}")
        return False
    console.print(f"[green]TSDB backfill complete.[/green] Output:\n{result.stdout}")
    return True


@click.command()
@click.option(
    "--scenario",
    type=click.Choice(["healthy", "outage", "degradation", "all"]),
    default="all",
    show_default=True,
    help="Scenario(s) to generate.",
)
@click.option("--days", default=7, show_default=True, help="Total history window in days.")
@click.option("--resolution", default=30, show_default=True, help="Sample interval in seconds.")
@click.option(
    "--outage-duration",
    default=30,
    show_default=True,
    help="Outage duration in minutes (for outage scenario).",
)
@click.option(
    "--output-dir",
    default="./output",
    show_default=True,
    help="Directory for CSV and OpenMetrics output files.",
)
@click.option(
    "--prometheus-data-dir",
    default=None,
    help="Prometheus TSDB data dir (for promtool backfill). "
    "Defaults to $PROMETHEUS_DATA_DIR env var.",
)
@click.option("--skip-influxdb", is_flag=True, default=False, help="Skip writing to InfluxDB.")
@click.option(
    "--skip-prometheus",
    is_flag=True,
    default=False,
    help="Skip writing Prometheus OpenMetrics file.",
)
@click.option(
    "--csv-only", is_flag=True, default=False, help="Write CSV only, skip all remote backends."
)
@click.option(
    "--run-promtool",
    is_flag=True,
    default=False,
    help="Run promtool TSDB backfill after generating OpenMetrics file.",
)
def main(
    scenario: str,
    days: int,
    resolution: int,
    outage_duration: int,
    output_dir: str,
    prometheus_data_dir: str | None,
    skip_influxdb: bool,
    skip_prometheus: bool,
    csv_only: bool,
    run_promtool: bool,
) -> None:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    prom_data_dir = Path(
        prometheus_data_dir or os.environ.get("PROMETHEUS_DATA_DIR", "/prometheus_data")
    )

    end_time = now_utc().replace(second=0, microsecond=0)
    start_time = end_time - timedelta(days=days)

    scenarios_to_run: list[str] = (
        ["healthy", "outage", "degradation"] if scenario == "all" else [scenario]
    )

    console.rule("[bold blue]SLO Test Data Generator[/bold blue]")
    console.print(
        f"Window: [cyan]{start_time.isoformat()}[/cyan] → [cyan]{end_time.isoformat()}[/cyan]"
    )
    console.print(
        f"Resolution: [cyan]{resolution}s[/cyan]  |  Scenarios: [cyan]{', '.join(scenarios_to_run)}[/cyan]"
    )
    console.print()

    all_om_files: list[Path] = []

    for scen_name in scenarios_to_run:
        console.rule(f"[bold]{scen_name.upper()}[/bold]")

        # ── Build scenario ──────────────────────────────────────────────
        if scen_name == "healthy":
            scen = HealthyScenario(start_time, end_time, resolution_seconds=resolution)
        elif scen_name == "outage":
            scen = OutageScenario(
                start_time,
                end_time,
                resolution_seconds=resolution,
                outage_duration_minutes=outage_duration,
            )
        elif scen_name == "degradation":
            scen = DegradationScenario(
                start_time,
                end_time,
                resolution_seconds=resolution,
            )
        else:
            console.print(f"[red]Unknown scenario: {scen_name}[/red]")
            continue

        # ── Generate samples ────────────────────────────────────────────
        sample_count = int((end_time - start_time).total_seconds() / resolution)
        console.print(f"Generating ~{sample_count:,} samples per series...")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(f"Generating {scen_name}...", total=None)
            families = scen.generate()
            progress.update(task, completed=True)

        total_samples = sum(len(f) for f in families.values())
        console.print(
            f"[green]Generated {total_samples:,} total samples across {len(families)} metric families.[/green]"
        )

        # ── Report per-family stats ─────────────────────────────────────
        table = Table(title="Metric Families")
        table.add_column("Metric", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Samples", justify="right")
        for name, fam in families.items():
            table.add_row(name, fam.metric_type.value, f"{len(fam):,}")
        console.print(table)

        # ── Write CSV ───────────────────────────────────────────────────
        csv_dir = output_path / "csv" / scen_name
        console.print(f"Writing CSV → [cyan]{csv_dir}[/cyan]")
        with CSVAdapter(csv_dir) as adapter:
            adapter.write(families)

        # ── Write Prometheus OpenMetrics ────────────────────────────────
        if not (skip_prometheus or csv_only):
            om_file = output_path / f"{scen_name}_metrics.om"
            console.print(f"Writing OpenMetrics → [cyan]{om_file}[/cyan]")
            with PrometheusAdapter(om_file) as adapter:
                adapter.write(families)
            all_om_files.append(om_file)
            console.print(
                f"[green]OpenMetrics file: {om_file.stat().st_size / 1024 / 1024:.1f} MB[/green]"
            )

        # ── Write InfluxDB ──────────────────────────────────────────────
        if not (skip_influxdb or csv_only):
            console.print("Writing to InfluxDB...")
            try:
                with InfluxDBAdapter() as adapter:
                    adapter.write(families)
                    adapter.ensure_dbrp_mapping()
                console.print("[green]InfluxDB write complete (DBRP mapping ensured).[/green]")
            except Exception as exc:
                console.print(f"[yellow]InfluxDB write failed (non-fatal): {exc}[/yellow]")

        console.print()

    # ── Run promtool TSDB backfill ──────────────────────────────────────
    if run_promtool and all_om_files:
        console.rule("[bold]Prometheus TSDB Backfill[/bold]")
        prom_data_dir.mkdir(parents=True, exist_ok=True)
        for om_file in all_om_files:
            ok = run_promtool_backfill(om_file, prom_data_dir)
            if not ok:
                console.print(f"[red]Backfill failed for {om_file}[/red]")
                sys.exit(1)
    elif not (skip_prometheus or csv_only) and all_om_files:
        console.print(
            "\n[yellow]Hint:[/yellow] To load data into Prometheus, run:\n"
            f"  promtool tsdb create-blocks-from openmetrics "
            f"{all_om_files[0]} {prom_data_dir}\n"
            "Or restart with [cyan]--run-promtool[/cyan] flag."
        )

    console.rule("[bold green]Done[/bold green]")


if __name__ == "__main__":
    main()
