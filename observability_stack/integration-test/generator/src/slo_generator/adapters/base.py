"""Base adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class BaseAdapter(ABC):
    """Receives shaped DataFrames and writes them to a backend."""

    @abstractmethod
    def write_chunk(self, df: pd.DataFrame) -> None:
        """Write one chunk."""
        ...

    def close(self) -> None:  # noqa: B027
        """Flush and release resources. Subclasses may override to flush/close handles."""

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
