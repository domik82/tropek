"""Base shaper interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator

import pandas as pd


class BaseShaper(ABC):
    """Transforms profile DataFrames into backend-specific metric DataFrames."""

    @abstractmethod
    def shape(self, profile_chunk: pd.DataFrame) -> Iterator[pd.DataFrame]:
        """Transform a profile chunk into shaped metric DataFrames."""
        ...

    def finalize(self) -> Iterator[pd.DataFrame]:
        """Flush any accumulated state. Override if stateful."""
        return iter([])
