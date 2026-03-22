"""Prometheus OpenMetrics adapter — writes shaped DataFrames to OpenMetrics format files."""

from __future__ import annotations

import contextlib
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

from slo_generator.adapters.base import BaseAdapter

# Metric family suffixes that indicate a histogram
_HISTOGRAM_SUFFIXES = ("_bucket", "_sum", "_count")

# Entry type alias: (metric_name, label_str, value, timestamp_epoch)
_Entry = tuple[str, str, float, float]


def _metric_family(metric: str) -> str:
    """Return the base family name for a metric (strips histogram suffixes)."""
    for suffix in _HISTOGRAM_SUFFIXES:
        if metric.endswith(suffix):
            return metric[: -len(suffix)]
    return metric


def _metric_type(metric: str) -> str:
    """Detect the OpenMetrics type for a metric name."""
    if metric.endswith("_total"):
        return "counter"
    for suffix in _HISTOGRAM_SUFFIXES:
        if metric.endswith(suffix):
            return "histogram"
    return "gauge"


def _is_na(value: Any) -> bool:
    """Return True if value is NA/None, suppressing type errors from pd.isna."""
    if value is None:
        return True
    result = False
    with contextlib.suppress(TypeError, ValueError):
        result = bool(pd.isna(value))
    return result


def _format_labels(row: pd.Series) -> str:
    """Build a sorted label string from a shaped DataFrame row.

    Label set rules (per PrometheusShaper output):
    - counters: instance, job, status_code (when present)
    - histogram buckets: instance, job, le
    - histogram sum/count: instance, job
    - gauges: instance, job
    """
    metric: str = str(row["metric"])
    labels: dict[str, str] = {
        "instance": str(row["instance"]),
        "job": str(row["job"]),
        "service": str(row["service"]),
        "host": str(row["host"]),
    }

    if metric.endswith("_bucket"):
        le = row["le"]
        if not _is_na(le):
            labels["le"] = str(le)

    is_histogram = any(metric.endswith(s) for s in _HISTOGRAM_SUFFIXES)
    if not is_histogram:
        status_code = row["status_code"]
        if not _is_na(status_code):
            labels["status_code"] = str(status_code)

    label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
    return "{" + label_str + "}"


def _timestamp_epoch(ts: Any) -> float:
    """Convert a pandas Timestamp (UTC) to Unix epoch seconds (float)."""
    return pd.Timestamp(ts).timestamp()


def _render_histogram_entries(entries: list[_Entry]) -> list[str]:
    """Render histogram family entries ordered as: buckets, sum, count."""
    bucket_lines: list[_Entry] = []
    sum_lines: list[_Entry] = []
    count_lines: list[_Entry] = []

    for entry in entries:
        metric_name = entry[0]
        if metric_name.endswith("_bucket"):
            bucket_lines.append(entry)
        elif metric_name.endswith("_sum"):
            sum_lines.append(entry)
        elif metric_name.endswith("_count"):
            count_lines.append(entry)

    rendered: list[str] = []
    for metric_name, label_str, value, ts in bucket_lines:
        rendered.append(f"{metric_name}{label_str} {value} {ts}")
    for metric_name, label_str, value, ts in sum_lines:
        rendered.append(f"{metric_name}{label_str} {value} {ts}")
    for metric_name, label_str, value, ts in count_lines:
        rendered.append(f"{metric_name}{label_str} {value} {ts}")
    return rendered


class PrometheusAdapter(BaseAdapter):
    """Writes Prometheus-shaped DataFrames to an OpenMetrics format file.

    Accumulates all chunks in memory and flushes to disk on ``close()``,
    grouping by metric family and emitting proper ``# TYPE`` / ``# HELP`` headers.
    Histogram families have bucket/sum/count lines ordered correctly.
    """

    def __init__(self, output_path: Path | str) -> None:
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        # family -> list of entries
        self._buffer: dict[str, list[_Entry]] = defaultdict(list)
        # track insertion order of families
        self._family_order: list[str] = []

    def write_chunk(self, df: pd.DataFrame) -> None:
        """Accumulate one shaped DataFrame chunk into the internal buffer."""
        for _, row in df.iterrows():
            metric = str(row["metric"])
            family = _metric_family(metric)
            if family not in self._buffer:
                self._family_order.append(family)
            label_str = _format_labels(row)
            value = float(row["value"])
            ts = _timestamp_epoch(row["timestamp"])
            self._buffer[family].append((metric, label_str, value, ts))

    def close(self) -> None:
        """Flush accumulated lines to the output file with OpenMetrics structure."""
        lines: list[str] = []

        for family in self._family_order:
            entries = self._buffer[family]
            if not entries:
                continue

            mtype = _metric_type(entries[0][0])
            lines.append(f"# HELP {family} Generated by slo_generator")
            lines.append(f"# TYPE {family} {mtype}")

            if mtype == "histogram":
                lines.extend(_render_histogram_entries(entries))
            else:
                for metric_name, label_str, value, ts in entries:
                    lines.append(f"{metric_name}{label_str} {value} {ts}")

        lines.append("# EOF")
        self.output_path.write_text("\n".join(lines) + "\n")

    @staticmethod
    def run_promtool(openmetrics_file: Path, data_dir: Path) -> subprocess.CompletedProcess[str]:
        """Run promtool to ingest an OpenMetrics file into a Prometheus TSDB block.

        Equivalent to:
            promtool tsdb create-blocks-from openmetrics <file> <data_dir>
        """
        return subprocess.run(  # noqa: S603
            [  # noqa: S607
                "promtool",
                "tsdb",
                "create-blocks-from",
                "openmetrics",
                str(openmetrics_file),
                str(data_dir),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
