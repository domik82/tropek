"""Prometheus adapter — emits OpenMetrics format files for TSDB backfill.

Usage flow:
  1. This adapter writes an OpenMetrics .om file
  2. Docker init container runs:
     promtool tsdb create-blocks-from openmetrics metrics.om /prometheus
  3. Prometheus starts with the pre-filled data directory

OpenMetrics format spec:
  https://github.com/OpenObservability/OpenMetrics/blob/main/specification/OpenMetrics.md

Key rules:
  - Counter samples MUST be monotonically increasing within a label set
  - Timestamps are in seconds (float) since Unix epoch
  - # EOF marker is required at end of file
"""

from __future__ import annotations

from pathlib import Path

from models import MetricFamily, MetricType

from adapters.base import BaseAdapter


class PrometheusAdapter(BaseAdapter):
    """Writes OpenMetrics text format suitable for promtool TSDB backfill.

    One file per scenario. The file is chunked into separate metric blocks
    as required by the OpenMetrics spec.
    """

    def __init__(self, output_path: str | Path):
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self.output_path, "w", encoding="utf-8")

    def write(self, families: dict[str, MetricFamily]) -> None:
        """Write all metric families to the OpenMetrics file."""
        # Group histogram families together (bucket, sum, count → same metric block)
        histogram_bases: set[str] = set()
        for name in families:
            if name.endswith("_bucket"):
                histogram_bases.add(name[: -len("_bucket")])

        written_families: set[str] = set()

        for name, family in families.items():
            if name in written_families:
                continue

            # Determine if this is part of a histogram
            base = None
            for hbase in histogram_bases:
                if name.startswith(hbase):
                    base = hbase
                    break

            if base and base not in written_families:
                # Write the full histogram block: bucket + sum + count
                self._write_histogram_family(
                    base,
                    families.get(f"{base}_bucket"),
                    families.get(f"{base}_sum"),
                    families.get(f"{base}_count"),
                )
                written_families.update([f"{base}_bucket", f"{base}_sum", f"{base}_count"])
            elif base:
                # Already written as part of the histogram block
                written_families.add(name)
            else:
                self._write_simple_family(family)
                written_families.add(name)

        # Required EOF marker
        self._file.write("# EOF\n")

    def _write_simple_family(self, family: MetricFamily) -> None:
        f = self._file
        om_type = {
            MetricType.COUNTER: "counter",
            MetricType.GAUGE: "gauge",
        }.get(family.metric_type, "unknown")

        f.write(f"# HELP {family.name} {family.help_text}\n")
        f.write(f"# TYPE {family.name} {om_type}\n")

        for sample in family.samples:
            label_str = self._format_labels(sample.labels)
            ts = sample.timestamp.timestamp()
            f.write(f"{family.name}{label_str} {sample.value:.6f} {ts:.3f}\n")

        f.write("\n")

    def _write_histogram_family(
        self,
        base_name: str,
        bucket_family: MetricFamily | None,
        sum_family: MetricFamily | None,
        count_family: MetricFamily | None,
    ) -> None:
        f = self._file
        f.write(f"# HELP {base_name} {base_name.replace('_', ' ')}\n")
        f.write(f"# TYPE {base_name} histogram\n")

        if bucket_family:
            for sample in bucket_family.samples:
                label_str = self._format_labels(sample.labels)
                ts = sample.timestamp.timestamp()
                f.write(f"{base_name}_bucket{label_str} {sample.value:.6f} {ts:.3f}\n")

        if sum_family:
            for sample in sum_family.samples:
                label_str = self._format_labels(sample.labels)
                ts = sample.timestamp.timestamp()
                f.write(f"{base_name}_sum{label_str} {sample.value:.6f} {ts:.3f}\n")

        if count_family:
            for sample in count_family.samples:
                label_str = self._format_labels(sample.labels)
                ts = sample.timestamp.timestamp()
                f.write(f"{base_name}_count{label_str} {sample.value:.6f} {ts:.3f}\n")

        f.write("\n")

    @staticmethod
    def _format_labels(labels: dict[str, str]) -> str:
        if not labels:
            return ""
        parts = [f'{k}="{v}"' for k, v in sorted(labels.items())]
        return "{" + ",".join(parts) + "}"

    def close(self) -> None:
        if not self._file.closed:
            self._file.close()
