"""InfluxDB adapter — writes shaped DataFrames using the InfluxDB line protocol."""

from __future__ import annotations

import contextlib
import os
from typing import Any

import pandas as pd

from slo_generator.adapters.base import BaseAdapter

try:
    from influxdb_client import InfluxDBClient
    from influxdb_client.client.write_api import SYNCHRONOUS

    _INFLUXDB_CLIENT_AVAILABLE = True
except ImportError:
    _INFLUXDB_CLIENT_AVAILABLE = False


def _is_na(value: Any) -> bool:
    """Return True if value is NA/None, suppressing type errors from pd.isna."""
    if value is None:
        return True
    result = False
    with contextlib.suppress(TypeError, ValueError):
        result = bool(pd.isna(value))
    return result


class InfluxDBAdapter(BaseAdapter):
    """Writes shaped DataFrames to InfluxDB using the line protocol.

    Connection parameters can be supplied via constructor arguments or
    environment variables (INFLUXDB_URL, INFLUXDB_TOKEN, INFLUXDB_ORG,
    INFLUXDB_BUCKET).

    The ``_to_line_protocol()`` static method has no dependency on the
    ``influxdb_client`` package and can be used (and tested) without a
    live connection.
    """

    def __init__(
        self,
        url: str | None = None,
        token: str | None = None,
        org: str | None = None,
        bucket: str | None = None,
    ) -> None:
        self._url = url or os.environ.get("INFLUXDB_URL", "http://localhost:8086")
        self._token = token or os.environ.get("INFLUXDB_TOKEN", "")
        self._org = org or os.environ.get("INFLUXDB_ORG", "")
        self._bucket = bucket or os.environ.get("INFLUXDB_BUCKET", "")
        self._client = None
        self._write_api = None
        self._dbrp_ensured = False

    # ------------------------------------------------------------------
    # Static / pure conversion — no connection required
    # ------------------------------------------------------------------

    @staticmethod
    def _to_line_protocol(df: pd.DataFrame) -> list[str]:
        """Convert a shaped DataFrame to a list of InfluxDB line protocol strings.

        Line protocol format::

            measurement,tag1=v1,tag2=v2 field1=value1 timestamp_ns

        Tags (included only when not NA):
            service, host, status_code

        Fields:
            value (always)

        Timestamp: nanosecond epoch integer.
        """
        lines: list[str] = []
        for _, row in df.iterrows():
            measurement = str(row["measurement"])

            # --- tags (sorted for determinism) ---
            tags: dict[str, str] = {}
            tags["host"] = str(row["host"])
            tags["service"] = str(row["service"])
            status_code = row.get("status_code", pd.NA)
            if not _is_na(status_code):
                tags["status_code"] = str(status_code)

            tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))

            # --- fields ---
            field_str = f"value={float(row['value'])}"

            # --- timestamp (nanoseconds) ---
            ts_ns = int(pd.Timestamp(row["timestamp"]).value)

            lines.append(f"{measurement},{tag_str} {field_str} {ts_ns}")
        return lines

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _connect(self) -> None:
        """Lazily initialise the InfluxDB client and write API."""
        if not _INFLUXDB_CLIENT_AVAILABLE:
            msg = (
                "influxdb-client is not installed; "
                "install slo-generator[influxdb] to use InfluxDBAdapter.write_chunk()"
            )
            raise ImportError(msg)
        if self._client is None:
            self._client = InfluxDBClient(
                url=self._url,
                token=self._token,
                org=self._org,
            )
            self._write_api = self._client.write_api(write_options=SYNCHRONOUS)

    def ensure_dbrp_mapping(self) -> None:
        """Create a DBRP mapping for the bucket (required for InfluxQL compatibility).

        Called automatically on the first ``write_chunk()`` invocation.
        No-op if the mapping already exists.
        """
        if self._dbrp_ensured:
            return
        self._connect()
        # Attempt to create a DBRP mapping; ignore errors if it already exists.
        with contextlib.suppress(Exception):
            dbrps_api = self._client.dbrps_api()  # type: ignore[union-attr]
            dbrps_api.create(
                db=self._bucket,
                rp="autogen",
                bucket_id=self._bucket,
                default=True,
                org=self._org,
            )
        self._dbrp_ensured = True

    # ------------------------------------------------------------------
    # BaseAdapter interface
    # ------------------------------------------------------------------

    def write_chunk(self, df: pd.DataFrame) -> None:
        """Convert *df* to line protocol and batch-write to InfluxDB."""
        self._connect()
        self.ensure_dbrp_mapping()
        lines = self._to_line_protocol(df)
        self._write_api.write(  # type: ignore[union-attr]
            bucket=self._bucket,
            org=self._org,
            record=lines,
            write_precision="ns",
        )

    def close(self) -> None:
        """Flush pending writes and close the client connection."""
        if self._write_api is not None:
            self._write_api.close()
        if self._client is not None:
            self._client.close()
