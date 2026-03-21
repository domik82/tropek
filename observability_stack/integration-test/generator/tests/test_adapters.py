"""Tests for adapters (I/O layer)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from slo_generator.adapters.csv import CSVAdapter


class TestCSVAdapter:
    def test_writes_dataframe_to_csv_file(self, tmp_path: Path, sample_profile_chunk: pd.DataFrame):
        output = tmp_path / "output.csv"
        with CSVAdapter(output) as adapter:
            adapter.write_chunk(sample_profile_chunk)

        result = pd.read_csv(output)
        assert len(result) == len(sample_profile_chunk)
        assert set(result.columns) == set(sample_profile_chunk.columns)

    def test_appends_multiple_chunks(self, tmp_path: Path, sample_profile_chunk: pd.DataFrame):
        output = tmp_path / "output.csv"
        with CSVAdapter(output) as adapter:
            adapter.write_chunk(sample_profile_chunk)
            adapter.write_chunk(sample_profile_chunk)

        result = pd.read_csv(output)
        assert len(result) == len(sample_profile_chunk) * 2
