"""Tests for metric shapers."""

from __future__ import annotations

import pandas as pd
from slo_generator.shapers.raw import RawShaper


class TestRawShaper:
    def test_passthrough_returns_same_data(self, sample_profile_chunk: pd.DataFrame):
        shaper = RawShaper()
        shaped = list(shaper.shape(sample_profile_chunk))
        assert len(shaped) == 1
        pd.testing.assert_frame_equal(shaped[0], sample_profile_chunk)

    def test_finalize_yields_nothing(self):
        shaper = RawShaper()
        assert list(shaper.finalize()) == []
