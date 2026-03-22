"""Base shaper interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator

import pandas as pd

from slo_generator.raw import RawChunk


class BaseShaper(ABC):
    """Transforms RawChunk data into backend-specific metric DataFrames."""

    @abstractmethod
    def shape(self, raw_chunk: RawChunk) -> Iterator[pd.DataFrame]:
        """Transform a raw chunk into shaped metric DataFrames."""
        ...

    def finalize(self) -> Iterator[pd.DataFrame]:
        """Flush any accumulated state. Override if stateful."""
        return iter([])
