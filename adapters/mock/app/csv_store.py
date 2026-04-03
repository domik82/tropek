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
        start: datetime,
        end: datetime,
    ) -> QueryResult:
        """Look up metric values within a time range.

        For each requested metric, finds all CSV rows in the namespace directory
        where start <= timestamp <= end and returns the last (most recent) value.
        """
        ns_dir = self._data_dir / namespace
        if not ns_dir.is_dir():
            return QueryResult(
                errors=dict.fromkeys(queries, f"namespace '{namespace}' not found"),
            )

        # Load all CSV rows from the namespace (cached after first read)
        rows = self._cache.get(namespace)
        if rows is None:
            rows = self._load_namespace(ns_dir)
            rows.sort(key=lambda r: r['timestamp'])
            self._cache[namespace] = rows

        result = QueryResult()
        for metric_name in queries:
            matching = [
                r for r in rows if r['metric_name'] == metric_name and start <= _parse_ts(r['timestamp']) <= end
            ]
            if matching:
                # Take the last value in the range (rows already sorted by timestamp)
                result.values[metric_name] = float(matching[-1]['value'])
            else:
                result.errors[metric_name] = f"no data for '{metric_name}' in range"

        return result

    def _load_namespace(self, ns_dir: Path) -> list[dict[str, str]]:
        """Load all CSV files in a namespace directory."""
        rows: list[dict[str, str]] = []
        for csv_path in ns_dir.glob('*.csv'):
            with csv_path.open() as f:
                reader = csv.DictReader(f)
                rows.extend(reader)
        return rows


def _parse_ts(ts_str: str) -> datetime:
    """Parse an ISO 8601 timestamp string to a timezone-aware datetime."""
    dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt
