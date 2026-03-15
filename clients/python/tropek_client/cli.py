"""CLI entrypoint for tropek client."""

from __future__ import annotations

import sys

import click

from tropek_client.client import TropekClient
from tropek_client.manifest import load_manifests, validate_manifests


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
    from tropek_client.manifest import apply as do_apply
    from tropek_client.manifest import dry_run as do_dry_run

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
