"""Raw shaper — converts RawChunk to DataFrame for CSV output."""

from __future__ import annotations

from collections.abc import Iterator

import pandas as pd

from slo_generator.raw import RawChunk
from slo_generator.shapers.base import BaseShaper


class RawShaper(BaseShaper):
    """Converts RawChunk into a flat DataFrame for CSV output.

    Output columns: timestamp, service, host, request_count, error_count,
    cpu_percent, memory_bytes
    """

    def shape(self, raw_chunk: RawChunk) -> Iterator[pd.DataFrame]:
        """Convert RawChunk to a DataFrame (latencies are dropped for CSV)."""
        if not raw_chunk:
            return

        rows = [
            {
                "timestamp": s.timestamp,
                "service": s.service,
                "host": s.host,
                "request_count": s.request_count,
                "error_count": s.error_count,
                "cpu_percent": s.cpu_percent,
                "memory_bytes": s.memory_bytes,
            }
            for s in raw_chunk
        ]
        yield pd.DataFrame(rows)
