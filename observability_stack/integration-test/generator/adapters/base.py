"""Base adapter interface — all adapters implement write()."""

from __future__ import annotations

from abc import ABC, abstractmethod

from models import MetricFamily


class BaseAdapter(ABC):
    """Receives a dict of MetricFamily objects and writes them to a backend."""

    @abstractmethod
    def write(self, families: dict[str, MetricFamily]) -> None:
        """Write all metric families to the backend."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Flush and release any resources."""
        ...

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
