"""TimescaleDB adapter — writes shaped DataFrames using psycopg COPY protocol."""

from __future__ import annotations

import os
from io import StringIO

import pandas as pd

from slo_generator.adapters.base import BaseAdapter

try:
    import psycopg

    _PSYCOPG_AVAILABLE = True
except ImportError:
    _PSYCOPG_AVAILABLE = False

_CREATE_TABLE_DDL = """\
CREATE TABLE IF NOT EXISTS metrics (
    timestamp TIMESTAMPTZ NOT NULL,
    metric TEXT NOT NULL,
    service TEXT NOT NULL,
    host TEXT NOT NULL,
    value DOUBLE PRECISION NOT NULL
);
SELECT create_hypertable('metrics', 'timestamp', if_not_exists => TRUE);\
"""


class TimescaleDBAdapter(BaseAdapter):
    """Writes shaped DataFrames to TimescaleDB using the psycopg COPY protocol.

    Connection DSN can be supplied via the constructor or the ``TIMESCALEDB_DSN``
    environment variable.

    The ``create_table_ddl()`` static method returns the DDL string and has
    no dependency on psycopg — it can be called and tested without a DB connection.
    """

    def __init__(self, dsn: str | None = None) -> None:
        self._dsn = dsn or os.environ.get("TIMESCALEDB_DSN", "")
        self._conn: object | None = None

    # ------------------------------------------------------------------
    # Static / pure DDL — no connection required
    # ------------------------------------------------------------------

    @staticmethod
    def create_table_ddl() -> str:
        """Return the CREATE TABLE + create_hypertable SQL for the metrics table."""
        return _CREATE_TABLE_DDL

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _connect(self) -> None:
        """Lazily open a psycopg connection and ensure the table exists."""
        if not _PSYCOPG_AVAILABLE:
            msg = (
                "psycopg is not installed; "
                "install slo-generator[timescaledb] to use TimescaleDBAdapter.write_chunk()"
            )
            raise ImportError(msg)
        if self._conn is None:
            self._conn = psycopg.connect(self._dsn)  # type: ignore[union-attr]
            with self._conn.cursor() as cur:  # type: ignore[union-attr]
                cur.execute(_CREATE_TABLE_DDL)
            self._conn.commit()  # type: ignore[union-attr]

    # ------------------------------------------------------------------
    # BaseAdapter interface
    # ------------------------------------------------------------------

    def write_chunk(self, df: pd.DataFrame) -> None:
        """Bulk-insert *df* into the metrics table using the COPY protocol."""
        self._connect()
        rows = df[["timestamp", "metric", "service", "host", "value"]]
        buf = StringIO()
        for _, row in rows.iterrows():
            ts = pd.Timestamp(row["timestamp"]).isoformat()
            buf.write(f"{ts}\t{row['metric']}\t{row['service']}\t{row['host']}\t{row['value']}\n")
        buf.seek(0)
        with (
            self._conn.cursor() as cur,  # type: ignore[union-attr]
            cur.copy(  # type: ignore[union-attr]
                "COPY metrics (timestamp, metric, service, host, value) FROM STDIN"
            ) as copy,
        ):
            copy.write(buf.read())
        self._conn.commit()  # type: ignore[union-attr]

    def close(self) -> None:
        """Close the psycopg connection."""
        if self._conn is not None:
            self._conn.close()  # type: ignore[union-attr]
            self._conn = None
