"""CLI entrypoint for tropek client."""

from __future__ import annotations

import sys
from typing import Any

import click
import yaml

from tropek_client.client import TropekClient
from tropek_client.manifest import (
    apply as do_apply,
)
from tropek_client.manifest import (
    dry_run as do_dry_run,
)
from tropek_client.manifest import (
    load_manifests,
    validate_manifests,
)


@click.group()
def cli() -> None:
    """TROPEK client CLI."""


@cli.command()
@click.option("-f", "--file", "path", required=True, help="YAML file or directory")
def validate(path: str) -> None:
    """Validate manifest syntax without making API calls."""
    errors = validate_manifests(path)
    if errors:
        for e in errors:
            click.echo(f"ERROR: {e}", err=True)
        sys.exit(1)
    docs = load_manifests(path)
    click.echo(f"Valid: {len(docs)} document(s)")


@cli.command()
@click.option("-f", "--file", "path", required=True, help="YAML file or directory")
@click.option("--base-url", default="http://localhost:8080", help="TROPEK API URL")
@click.option("--dry-run", is_flag=True, help="Show what would change without applying")
@click.option("--api-key", default=None, help="API key for authentication")
def apply(path: str, base_url: str, dry_run: bool, api_key: str | None) -> None:
    """Apply manifests to a TROPEK instance."""
    docs = load_manifests(path)
    with TropekClient(base_url=base_url, api_key=api_key) as client:
        if dry_run:
            plan = do_dry_run(client, docs)
            for action in plan.actions:
                click.echo(f"{action.operation:6s}  {action.kind}/{action.name}  {action.reason}")
            return

        result = do_apply(client, docs)
        click.echo(
            f"{result.created} created, {result.updated} updated, "
            f"{result.skipped} skipped, {result.failed} failed"
        )
        if result.errors:
            for err in result.errors:
                click.echo(f"  ERROR: {err.kind}/{err.name}: {err.error}", err=True)
            sys.exit(1)


def _collect_documents(client: TropekClient) -> list[dict[str, Any]]:
    """Collect all resources from a TROPEK instance as manifest documents."""
    documents: list[dict[str, Any]] = []

    documents.extend(
        {
            "api_version": "tropek/v1",
            "kind": "AssetType",
            "metadata": {"name": at.name},
            "spec": {"is_default": at.is_default},
        }
        for at in client.asset_types.list()
    )
    documents.extend(
        {
            "api_version": "tropek/v1",
            "kind": "DataSource",
            "metadata": {"name": ds.name, "display_name": ds.display_name, "tags": ds.tags},
            "spec": {"adapter_type": ds.adapter_type, "adapter_url": ds.adapter_url},
        }
        for ds in client.datasources.list().items
    )
    documents.extend(
        {
            "api_version": "tropek/v1",
            "kind": "Asset",
            "metadata": {"name": a.name, "display_name": a.display_name, "tags": a.tags},
            "spec": {"type_name": a.type_name},
        }
        for a in client.assets.list().items
    )
    documents.extend(
        {
            "api_version": "tropek/v1",
            "kind": "SLI",
            "metadata": {
                "name": s.name,
                "display_name": s.display_name,
                "notes": s.notes,
                "author": s.author,
            },
            "spec": {"indicators": s.indicators},
        }
        for s in client.sli_definitions.list().items
    )
    for slo in client.slo_definitions.list().items:
        objectives = [
            {k: v for k, v in o.model_dump().items() if k != "sort_order"} for o in slo.objectives
        ]
        documents.append(
            {
                "api_version": "tropek/v1",
                "kind": "SLO",
                "metadata": {
                    "name": slo.name,
                    "display_name": slo.display_name,
                    "notes": slo.notes,
                    "author": slo.author,
                },
                "spec": {
                    "total_score": {
                        "pass_pct": slo.total_score_pass_pct,
                        "warning_pct": slo.total_score_warning_pct,
                    },
                    "objectives": objectives,
                    **({"comparison": slo.comparison} if slo.comparison else {}),
                },
            }
        )
    documents.extend(
        {
            "api_version": "tropek/v1",
            "kind": "AssetGroup",
            "metadata": {"name": g.name, "display_name": g.display_name},
            "spec": {},
        }
        for g in client.asset_groups.list().items
    )
    documents.extend(
        {
            "api_version": "tropek/v1",
            "kind": "AssetSLOLink",
            "metadata": {"name": link.link_name},
            "spec": {
                "asset_name": asset.name,
                "slo_name": link.slo_name,
                "sli_name": link.sli_name,
                "data_source_name": link.data_source_name,
            },
        }
        for asset in client.assets.list().items
        for link in client.asset_slo_links.list(asset.name)
    )
    documents.extend(
        {
            "api_version": "tropek/v1",
            "kind": "AssetGroupSLOLink",
            "metadata": {"name": link.link_name},
            "spec": {
                "group_name": group.name,
                "slo_name": link.slo_name,
                "sli_name": link.sli_name,
                "data_source_name": link.data_source_name,
            },
        }
        for group in client.asset_groups.list().items
        for link in client.group_slo_links.list(group.name)
    )
    return documents


@cli.command()
@click.option("-f", "--file", "path", default=None, help="Output file (default: stdout)")
@click.option("--base-url", default="http://localhost:8080", help="TROPEK API URL")
@click.option("--api-key", default=None, help="API key for authentication")
def export(path: str | None, base_url: str, api_key: str | None) -> None:
    """Export all resources from a TROPEK instance as manifest YAML."""
    with TropekClient(base_url=base_url, api_key=api_key) as client:
        documents = _collect_documents(client)

    output = yaml.dump_all(documents, default_flow_style=False, allow_unicode=True)
    if path:
        with open(path, "w", encoding="utf-8") as f:
            f.write(output)
        click.echo(f"Exported {len(documents)} document(s) to {path}")
    else:
        click.echo(output, nl=False)
