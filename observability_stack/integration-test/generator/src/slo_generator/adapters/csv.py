"""CSV adapter — writes DataFrames to CSV files."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from slo_generator.adapters.base import BaseAdapter


class CSVAdapter(BaseAdapter):
    """Writes DataFrames to a CSV file, appending chunks."""

    def __init__(self, output_path: Path | str):
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._header_written = False

    def write_chunk(self, df: pd.DataFrame) -> None:
        """Append one DataFrame chunk to the CSV file."""
        df.to_csv(
            self.output_path,
            mode="a" if self._header_written else "w",
            header=not self._header_written,
            index=False,
        )
        self._header_written = True
