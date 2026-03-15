"""CLI entry point for tropek-client."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from tropek_client.client import TropekClient
from tropek_client.manifest import apply, load_manifest


@click.group()
@click.option("--url", default="http://localhost:8080", envvar="TROPEK_URL", show_default=True)
@click.option("--api-key", default=None, envvar="TROPEK_API_KEY")
@click.pass_context
def cli(ctx: click.Context, url: str, api_key: str | None) -> None:
    """TROPEK command-line interface."""
    ctx.ensure_object(dict)
    ctx.obj["url"] = url
    ctx.obj["api_key"] = api_key


@cli.command()
@click.argument("manifest", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--dry-run", is_flag=True, default=False, help="Show planned actions without applying"
)
@click.pass_context
def apply_cmd(ctx: click.Context, manifest: Path, dry_run: bool) -> None:
    """Apply a YAML manifest to the TROPEK API."""
    resources = load_manifest(manifest)
    click.echo(f"Loaded {len(resources)} resource(s) from {manifest}")

    with TropekClient(ctx.obj["url"], api_key=ctx.obj["api_key"]) as client:
        result = apply(client, resources, dry_run=dry_run)

    for action in result.actions:
        icon = {"create": "+", "update": "~", "skip": "="}[action.action.value]
        click.echo(f"  [{icon}] {action.kind.value}/{action.name}: {action.reason}")

    if result.errors:
        for err in result.errors:
            click.echo(f"  [!] {err}", err=True)
        sys.exit(1)

    if dry_run:
        click.echo("Dry run complete — no changes applied.")
    else:
        click.echo("Apply complete.")


# Register apply_cmd as "apply" subcommand
cli.add_command(apply_cmd, name="apply")


@cli.command()
@click.argument("manifest", type=click.Path(exists=True, path_type=Path))
@click.pass_context
def validate(ctx: click.Context, manifest: Path) -> None:
    """Validate a YAML manifest and all SLO definitions within it."""
    resources = load_manifest(manifest)
    click.echo(f"Loaded {len(resources)} resource(s) from {manifest}")

    with TropekClient(ctx.obj["url"], api_key=ctx.obj["api_key"]) as client:
        errors_found = False
        for resource in resources:
            from tropek_client.manifest import ResourceKind

            if resource.kind == ResourceKind.SLO_DEFINITION:
                slo_yaml = resource.spec.get("slo_yaml", "")
                result = client.slo.validate(slo_yaml)
                if result.valid:
                    click.echo(f"  [ok] {resource.name}: valid")
                else:
                    errors_found = True
                    click.echo(f"  [fail] {resource.name}:")
                    for err in result.errors:
                        click.echo(f"    - {err.field}: {err.message}")

    if errors_found:
        sys.exit(1)
    click.echo("All definitions valid.")
