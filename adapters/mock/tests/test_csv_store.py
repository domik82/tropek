"""Unit tests for the CSV data store."""

from __future__ import annotations

import csv
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from tropek_mock.csv_store import CsvStore


def _write_csv(directory: Path, namespace: str, rows: list[dict[str, str]]) -> None:
    """Write test CSV data into namespace directory."""
    ns_dir = directory / namespace
    ns_dir.mkdir(parents=True, exist_ok=True)
    path = ns_dir / 'metrics.csv'
    with path.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['timestamp', 'metric_name', 'value'])
        writer.writeheader()
        writer.writerows(rows)


def test_lookup_returns_last_value_in_range() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        _write_csv(
            data_dir,
            'prom-dc-a',
            [
                {'timestamp': '2026-03-15T08:00:00Z', 'metric_name': 'cpu', 'value': '40.0'},
                {'timestamp': '2026-03-15T08:05:00Z', 'metric_name': 'cpu', 'value': '45.0'},
                {'timestamp': '2026-03-15T08:10:00Z', 'metric_name': 'cpu', 'value': '50.0'},
                {'timestamp': '2026-03-15T09:00:00Z', 'metric_name': 'cpu', 'value': '60.0'},
            ],
        )
        store = CsvStore(data_dir)
        result = store.query(
            namespace='prom-dc-a',
            queries={'cpu': 'ignored_query_string'},
            start=datetime(2026, 3, 15, 8, 0, tzinfo=UTC),
            end=datetime(2026, 3, 15, 8, 15, tzinfo=UTC),
        )
        assert result.values == {'cpu': 50.0}
        assert result.errors == {}


def test_missing_metric_goes_to_errors() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        _write_csv(
            data_dir,
            'prom-dc-a',
            [
                {'timestamp': '2026-03-15T08:00:00Z', 'metric_name': 'cpu', 'value': '40.0'},
            ],
        )
        store = CsvStore(data_dir)
        result = store.query(
            namespace='prom-dc-a',
            queries={'cpu': 'q1', 'missing_metric': 'q2'},
            start=datetime(2026, 3, 15, 8, 0, tzinfo=UTC),
            end=datetime(2026, 3, 15, 8, 15, tzinfo=UTC),
        )
        assert result.values == {'cpu': 40.0}
        assert 'missing_metric' in result.errors


def test_unknown_namespace_all_errors() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = CsvStore(Path(tmpdir))
        result = store.query(
            namespace='nonexistent',
            queries={'cpu': 'q'},
            start=datetime(2026, 3, 15, 8, 0, tzinfo=UTC),
            end=datetime(2026, 3, 15, 8, 15, tzinfo=UTC),
        )
        assert result.values == {}
        assert 'cpu' in result.errors
