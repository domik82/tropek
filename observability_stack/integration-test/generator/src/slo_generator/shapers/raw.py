"""Raw shaper — passthrough for CSV output."""

from __future__ import annotations

from collections.abc import Iterator

import pandas as pd

from slo_generator.shapers.base import BaseShaper


class RawShaper(BaseShaper):
    """Passes profile DataFrame through unchanged."""

    def shape(self, profile_chunk: pd.DataFrame) -> Iterator[pd.DataFrame]:
        """Yield the profile chunk unchanged."""
        yield profile_chunk
