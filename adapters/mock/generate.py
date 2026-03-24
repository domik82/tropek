"""Generate CSV time-series data from scenario YAML definitions."""

from __future__ import annotations

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

import yaml


def load_scenario(path: Path) -> dict:
    """Load a scenario YAML file."""
    with path.open() as f:
        return yaml.safe_load(f)


def generate_scenario_rows(scenario: dict) -> list[dict[str, str]]:
    """Generate time-series rows from a scenario definition.

    Uses the scenario name as the random seed for deterministic output.
    Returns rows without writing — caller is responsible for merging and writing.
    """
    rng = random.Random(scenario["name"])  # noqa: S311
    interval = timedelta(minutes=scenario["interval_minutes"])
    start = datetime.fromisoformat(scenario["start"].replace("Z", "+00:00"))

    all_rows: list[dict[str, str]] = []
    for metric_name, metric_def in scenario["metrics"].items():
        baseline = metric_def["baseline"]
        current_time = start
        for phase in metric_def["phases"]:
            duration = timedelta(hours=phase["duration_hours"])
            phase_end = current_time + duration
            jitter_pct = phase["jitter_pct"] / 100.0
            pattern = phase["pattern"]
            target = phase.get("target", baseline)
            phase_start_time = current_time
            while current_time < phase_end:
                if pattern == "stable":
                    value = baseline * (1.0 + rng.uniform(-jitter_pct, jitter_pct))
                elif pattern == "ramp":
                    progress = (current_time - phase_start_time) / duration
                    value = baseline + (target - baseline) * progress
                    value *= 1.0 + rng.uniform(-jitter_pct, jitter_pct)
                elif pattern == "spike":
                    mid = phase_start_time + duration / 2
                    if current_time < mid:
                        progress = (current_time - phase_start_time) / (duration / 2)
                        value = baseline + (target - baseline) * progress
                    else:
                        progress = (current_time - mid) / (duration / 2)
                        value = target + (baseline - target) * progress
                    value *= 1.0 + rng.uniform(-jitter_pct, jitter_pct)
                else:
                    value = baseline
                all_rows.append(
                    {
                        "timestamp": current_time.isoformat(),
                        "metric_name": metric_name,
                        "value": f"{value:.6f}",
                    }
                )
                current_time += interval
            # Update baseline for next phase (ramp endpoint becomes new baseline)
            if pattern == "ramp":
                baseline = target

    return all_rows


def main() -> None:
    """Generate CSVs for all scenarios into the data directory.

    Accumulates rows per namespace across all scenarios so that multiple
    scenarios targeting the same namespace are merged into one CSV.
    """
    scenarios_dir = Path("scenarios")
    data_dir = Path("data")
    ns_rows: dict[str, list[dict[str, str]]] = {}
    ns_sources: dict[str, list[str]] = {}

    for scenario_path in sorted(scenarios_dir.glob("*.yaml")):
        scenario = load_scenario(scenario_path)
        rows = generate_scenario_rows(scenario)
        namespaces = scenario.get("namespaces", [scenario["name"]])
        for ns in namespaces:
            ns_rows.setdefault(ns, []).extend(rows)
            ns_sources.setdefault(ns, []).append(scenario["name"])

    for ns, rows in ns_rows.items():
        ns_dir = data_dir / ns
        ns_dir.mkdir(parents=True, exist_ok=True)
        rows.sort(key=lambda r: (r["timestamp"], r["metric_name"]))
        csv_path = ns_dir / "metrics.csv"
        with csv_path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["timestamp", "metric_name", "value"])
            writer.writeheader()
            writer.writerows(rows)
        sources = ", ".join(ns_sources[ns])
        print(f"generated {csv_path} ({sources})")


if __name__ == "__main__":
    main()
