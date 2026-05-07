"""CSV-backed time-series data store for the mock adapter."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class QueryResult:
    """Result of a metric query — mirrors the adapter response contract."""

    values: dict[str, float] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)


class CsvStore:
    """Reads CSV files from namespace directories and performs time-range lookups."""

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._cache: dict[str, list[dict[str, str]]] = {}

    def query(
        self,
        *,
        namespace: str,
        queries: dict[str, str],
        variables: dict[str, str] | None = None,
        start: datetime,
        end: datetime,
    ) -> QueryResult:
        """Look up metric values within a time range.

        For each requested metric, finds all CSV rows in the namespace directory
        where start <= timestamp <= end and returns the last (most recent) value.
        When variables are provided, rows with a matching variable_key are
        preferred over unkeyed rows.
        """
        ns_dir = self._data_dir / namespace
        if not ns_dir.is_dir():
            return QueryResult(
                errors=dict.fromkeys(queries, f"namespace '{namespace}' not found"),
            )

        rows = self._cache.get(namespace)
        if rows is None:
            rows = self._load_namespace(ns_dir)
            rows.sort(key=lambda r: r['timestamp'])
            self._cache[namespace] = rows

        variable_keys = _build_variable_keys(variables or {})

        result = QueryResult()
        for metric_name in queries:
            matching = [
                r for r in rows if r['metric_name'] == metric_name and start <= _parse_ts(r['timestamp']) <= end
            ]
            if not matching:
                result.errors[metric_name] = f"no data for '{metric_name}' in range"
                continue

            keyed = [r for r in matching if r.get('variable_key', '') in variable_keys] if variable_keys else []
            best = keyed if keyed else [r for r in matching if not r.get('variable_key', '')]
            if best:
                result.values[metric_name] = float(best[-1]['value'])
            else:
                result.values[metric_name] = float(matching[-1]['value'])

        return result

    def _load_namespace(self, ns_dir: Path) -> list[dict[str, str]]:
        """Load all CSV files in a namespace directory."""
        rows: list[dict[str, str]] = []
        for csv_path in ns_dir.glob('*.csv'):
            with csv_path.open() as f:
                reader = csv.DictReader(f)
                rows.extend(reader)
        return rows


def _build_variable_keys(variables: dict[str, str]) -> set[str]:
    """Build the set of variable_key strings to match against CSV rows."""
    return {f'{k}={v}' for k, v in variables.items()} if variables else set()


def _parse_ts(ts_str: str) -> datetime:
    """Parse an ISO 8601 timestamp string to a timezone-aware datetime."""
    dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt
