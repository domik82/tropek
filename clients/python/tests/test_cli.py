from __future__ import annotations

from unittest.mock import MagicMock

import tropek_client.cli as cli_mod
from click.testing import CliRunner
from tropek_client.cli import cli
from tropek_client.manifest import ApplyPlan, PlanAction


def test_validate_valid_manifest(tmp_path):
    f = tmp_path / 'test.yaml'
    f.write_text("""
api_version: tropek/v1
kind: AssetType
metadata:
  name: vm
spec:
  is_default: true
""")
    runner = CliRunner()
    result = runner.invoke(cli, ['validate', '-f', str(f)])
    assert result.exit_code == 0
    assert 'valid' in result.output.lower()


def test_validate_invalid_manifest(tmp_path):
    f = tmp_path / 'test.yaml'
    f.write_text("""
kind: AssetType
metadata:
  name: vm
""")
    runner = CliRunner()
    result = runner.invoke(cli, ['validate', '-f', str(f)])
    assert result.exit_code != 0


def test_apply_dry_run(tmp_path, monkeypatch):
    f = tmp_path / 'test.yaml'
    f.write_text("""
api_version: tropek/v1
kind: AssetType
metadata:
  name: vm
spec:
  is_default: true
""")
    mock_client = MagicMock()
    mock_plan = ApplyPlan(
        actions=[
            PlanAction(operation='CREATE', kind='AssetType', name='vm', reason='not found in current state'),
        ]
    )

    monkeypatch.setattr(cli_mod, 'TropekClient', lambda **kw: mock_client)

    monkeypatch.setattr('tropek_client.manifest.dry_run', lambda c, d: mock_plan)

    runner = CliRunner()
    result = runner.invoke(cli, ['apply', '--dry-run', '-f', str(f)])
    assert result.exit_code == 0
    assert 'CREATE' in result.output
    assert 'AssetType/vm' in result.output
