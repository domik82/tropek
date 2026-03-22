"""CSV input scenario — reads a user-provided CSV as a profile DataFrame."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pandas as pd

from slo_generator.constants import HOSTS, PROFILE_COLUMNS, SERVICES


class CSVScenario:
    """Reads a CSV file and yields it as profile DataFrames.

    The CSV must contain all profile columns. Timestamps are parsed to UTC.
    Data is yielded in 1-hour chunks.
    """

    name = "csv"

    def __init__(self, csv_path: Path | str):
        self.csv_path = Path(csv_path)
        self._validate()

    def _validate(self) -> None:
        """Check that the CSV has the required columns."""
        df_head = pd.read_csv(self.csv_path, nrows=2)
        required = set(PROFILE_COLUMNS)
        actual = set(df_head.columns)
        missing = required - actual
        if missing:
            raise ValueError(f"missing columns in {self.csv_path.name}: {sorted(missing)}")

    def generate(self, resolution_seconds: int = 1) -> Iterator[pd.DataFrame]:
        """Read CSV in chunks and yield profile DataFrames."""
        for chunk in pd.read_csv(
            self.csv_path,
            parse_dates=["timestamp"],
            chunksize=21_600,  # ~1 hour at 1s with 6 service-host combos
        ):
            chunk["timestamp"] = pd.to_datetime(chunk["timestamp"], utc=True).astype(
                "datetime64[ns, UTC]"
            )
            chunk["service"] = pd.Categorical(chunk["service"], categories=SERVICES)
            chunk["host"] = pd.Categorical(chunk["host"], categories=HOSTS)
            yield chunk[PROFILE_COLUMNS]
