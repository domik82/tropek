#!/usr/bin/env python3
"""Generate Grafana dashboard JSON files from a config YAML for multiple datasources."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

DATASOURCES: dict[str, dict[str, str]] = {
    "prometheus": {
        "type": "prometheus",
        "uid": "prometheus",
        "query_key": "prometheus",
    },
    "influxdb": {
        "type": "influxdb",
        "uid": "influxdb",
        "query_key": "influxql",
    },
    "timescaledb": {
        "type": "grafana-postgresql-datasource",
        "uid": "timescaledb",
        "query_key": "sql",
    },
}

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "dashboard_config.yaml"
TEMPLATES_DIR = BASE_DIR / "templates"
OUTPUT_DIR = BASE_DIR / "dashboards"


def get_time_range(metadata_path: Path | None) -> tuple[str, str]:
    """Compute dashboard time range from metadata JSON, or fall back to relative defaults.

    If metadata_path exists and contains an ``end`` timestamp, computes start as
    end minus 7 days and returns both as ISO 8601 strings with a "Z" suffix.
    Falls back to ("now-7d", "now") if no metadata is available.
    """
    if metadata_path is not None and metadata_path.exists():
        with open(metadata_path) as f:
            metadata = json.load(f)
        end_str = metadata.get("end")
        if end_str:
            end_dt = datetime.fromisoformat(end_str.rstrip("Z")).replace(tzinfo=UTC)
            start_dt = end_dt - timedelta(days=7)
            return (
                start_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                end_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
    return ("now-7d", "now")


def load_config(path: Path, metadata_path: Path | None = None) -> dict:
    """Load and parse the dashboard YAML config file, optionally overriding time range."""
    with open(path) as f:
        config = yaml.safe_load(f)
    time_from, time_to = get_time_range(metadata_path)
    config["time_from"] = time_from
    config["time_to"] = time_to
    return config


def render_dashboard(
    config: dict,
    datasource_name: str,
    datasource_type: str,
    datasource_uid: str,
    query_key: str,
    env: Environment,
) -> str:
    """Render a single dashboard JSON string for the given datasource."""
    template = env.get_template("dashboard.json.j2")
    return template.render(
        title=config["title"],
        uid=config["uid"],
        refresh=config["refresh"],
        time_from=config["time_from"],
        time_to=config["time_to"],
        variables=config.get("variables", []),
        panels=config["panels"],
        datasource_name=datasource_name,
        datasource_type=datasource_type,
        datasource_uid=datasource_uid,
        query_key=query_key,
    )


def validate_json(content: str, output_path: Path) -> bool:
    """Validate that rendered content is valid JSON. Returns True on success."""
    try:
        json.loads(content)
        return True
    except json.JSONDecodeError as exc:
        print(f"  WARNING: rendered JSON is invalid for {output_path.name}: {exc}")
        return False


def generate_all_dashboards(metadata_path: Path | None = None) -> None:
    """Render one dashboard JSON file per datasource and write to the output directory."""
    config = load_config(CONFIG_PATH, metadata_path=metadata_path)
    OUTPUT_DIR.mkdir(exist_ok=True)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(enabled_extensions=()),  # JSON output, no HTML escaping
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )

    dashboard_uid = config.get("uid", "slo-test")

    for ds_name, ds_config in DATASOURCES.items():
        output_path = OUTPUT_DIR / f"{dashboard_uid}_{ds_name}.json"

        rendered = render_dashboard(
            config=config,
            datasource_name=ds_name,
            datasource_type=ds_config["type"],
            datasource_uid=ds_config["uid"],
            query_key=ds_config["query_key"],
            env=env,
        )

        valid = validate_json(rendered, output_path)

        with open(output_path, "w") as f:
            f.write(rendered)

        status = "OK" if valid else "INVALID JSON"
        print(f"  [{status}] {output_path.relative_to(BASE_DIR)}")


if __name__ == "__main__":
    metadata_path: Path | None = None
    if "--metadata" in sys.argv:
        idx = sys.argv.index("--metadata")
        if idx + 1 < len(sys.argv):
            metadata_path = Path(sys.argv[idx + 1])

    print(f"Generating dashboards from {CONFIG_PATH.relative_to(BASE_DIR)}")
    print(f"Output directory: {OUTPUT_DIR.relative_to(BASE_DIR)}/")
    if metadata_path is not None:
        print(f"Metadata: {metadata_path}")
    print()
    generate_all_dashboards(metadata_path=metadata_path)
    print()
    print("Done.")
