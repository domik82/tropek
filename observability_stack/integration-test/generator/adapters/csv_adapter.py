"""CSV adapter — writes one CSV file per metric family."""

from __future__ import annotations

import csv
from pathlib import Path

from models import MetricFamily

from adapters.base import BaseAdapter


class CSVAdapter(BaseAdapter):
    """Writes metric samples to CSV files.

    Output structure:
      output_dir/
        http_requests_total.csv
        http_errors_total.csv
        ...

    CSV format:
      timestamp,label_1,label_2,...,value

    Labels are discovered from the first sample in each family and used
    as column headers. All samples in a family must have the same label set.
    """

    def __init__(self, output_dir: str | Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write(self, families: dict[str, MetricFamily]) -> None:
        for name, family in families.items():
            if not family.samples:
                continue
            self._write_family(name, family)

    def _write_family(self, name: str, family: MetricFamily) -> None:
        output_path = self.output_dir / f"{name}.csv"

        # Discover all label keys from all samples (union)
        all_label_keys: list[str] = []
        seen: set[str] = set()
        for sample in family.samples:
            for key in sample.labels:
                if key not in seen:
                    all_label_keys.append(key)
                    seen.add(key)

        header = ["timestamp", "timestamp_unix"] + all_label_keys + ["value"]

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            for sample in family.samples:
                row = (
                    [
                        sample.timestamp.isoformat(),
                        f"{sample.timestamp.timestamp():.3f}",
                    ]
                    + [sample.labels.get(k, "") for k in all_label_keys]
                    + [f"{sample.value:.6f}"]
                )
                writer.writerow(row)

    def close(self) -> None:
        pass  # no persistent resources
