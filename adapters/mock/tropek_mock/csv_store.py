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
            rows_in_range = [
                row for row in rows if row['metric_name'] == metric_name and start <= _parse_ts(row['timestamp']) <= end
            ]
            if not rows_in_range:
                result.errors[metric_name] = f"no data for '{metric_name}' in range"
                continue

            # Variable-key resolution: CSV rows can carry a variable_key column
            # (e.g. "env=prod") that scopes them to a specific variable binding.
            # When the caller passes variables, we prefer rows whose key matches;
            # otherwise we fall back to unkeyed (global) rows, and finally to
            # any row at all so we never silently drop data.
            rows_matching_variable_key = (
                [row for row in rows_in_range if row.get('variable_key', '') in variable_keys] if variable_keys else []
            )
            rows_without_variable_key = [row for row in rows_in_range if not row.get('variable_key', '')]

            # Priority: variable-keyed rows > unkeyed rows > any row
            preferred_rows = rows_matching_variable_key or rows_without_variable_key
            if preferred_rows:
                result.values[metric_name] = float(preferred_rows[-1]['value'])
            else:
                result.values[metric_name] = float(rows_in_range[-1]['value'])

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
    """Convert caller's variable dict into the flat string format stored in CSV rows.

    The caller passes variables as a dict (e.g. {"process_name": "WINWORD"})
    but CSV rows store them as a single string column "process_name=WINWORD".
    This builds the set of those strings so we can do O(1) membership checks.
    """
    return {f'{name}={value}' for name, value in variables.items()} if variables else set()


def _parse_ts(ts_str: str) -> datetime:
    """Parse an ISO 8601 timestamp string to a timezone-aware datetime."""
    dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt
