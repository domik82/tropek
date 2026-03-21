#!/usr/bin/env python3
"""Generate Grafana dashboard JSON files from a config YAML for multiple datasources."""

from __future__ import annotations

import json
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
        "type": "postgres",
        "uid": "timescaledb",
        "query_key": "sql",
    },
}

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "dashboard_config.yaml"
TEMPLATES_DIR = BASE_DIR / "templates"
OUTPUT_DIR = BASE_DIR / "dashboards"


def load_config(path: Path) -> dict:
    """Load and parse the dashboard YAML config file."""
    with open(path) as f:
        return yaml.safe_load(f)


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


def generate_all_dashboards() -> None:
    """Render one dashboard JSON file per datasource and write to the output directory."""
    config = load_config(CONFIG_PATH)
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
    print(f"Generating dashboards from {CONFIG_PATH.relative_to(BASE_DIR)}")
    print(f"Output directory: {OUTPUT_DIR.relative_to(BASE_DIR)}/")
    print()
    generate_all_dashboards()
    print()
    print("Done.")
