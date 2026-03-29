"""InfluxDB v2 adapter — writes samples using the InfluxDB Python client.

InfluxDB receives 1-second samples (or whatever resolution the scenario uses).
Line protocol format:
  measurement,tag_key=tag_val field_key=field_val timestamp_ns

Counter metrics are written as their delta per interval (rate), not cumulative,
since InfluxDB handles non-monotonic data differently than Prometheus.

After writing, the adapter creates a DBRP mapping so InfluxQL queries work
against the v2 bucket (required for Grafana InfluxQL datasource).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.domain.write_precision import WritePrecision
from models import MetricFamily, MetricType

from adapters.base import BaseAdapter

# Batch size for writes — InfluxDB performs best with large batches
WRITE_BATCH_SIZE = 5000


class InfluxDBAdapter(BaseAdapter):
    """Writes metric samples to InfluxDB 2.x.

    Each MetricFamily becomes an InfluxDB measurement.
    Labels map to InfluxDB tags.
    The metric value is stored in a field named 'value'.

    Counter families are written as-is (cumulative value) in the
    'value' field, plus a computed 'rate' field showing the per-second
    derivative where possible.
    """

    def __init__(
        self,
        url: str | None = None,
        token: str | None = None,
        org: str | None = None,
        bucket: str | None = None,
    ):
        self.url = url or os.environ.get("INFLUXDB_URL", "http://localhost:8086")
        self.token = token or os.environ.get("INFLUXDB_TOKEN", "slo-test-token")
        self.org = org or os.environ.get("INFLUXDB_ORG", "slo-org")
        self.bucket = bucket or os.environ.get("INFLUXDB_BUCKET", "slo-metrics")

        self._client = InfluxDBClient(url=self.url, token=self.token, org=self.org)
        self._write_api = self._client.write_api(write_options=SYNCHRONOUS)

    def write(self, families: dict[str, MetricFamily]) -> None:
        """Write all families to InfluxDB in batches."""
        records: list[str] = []

        for name, family in families.items():
            measurement = name.replace(".", "_")
            prev_values: dict[str, float] = {}
            prev_ts: dict[str, float] = {}

            for sample in family.samples:
                ts_ns = int(sample.timestamp.timestamp() * 1_000_000_000)
                tag_str = self._format_tags(sample.labels)
                label_key = str(sorted(sample.labels.items()))

                if family.metric_type == MetricType.COUNTER:
                    # Write cumulative value
                    fields = f"value={sample.value:.6f}"

                    # Compute rate if we have a previous sample
                    if label_key in prev_values and label_key in prev_ts:
                        delta_val = sample.value - prev_values[label_key]
                        delta_t = sample.timestamp.timestamp() - prev_ts[label_key]
                        if delta_t > 0 and delta_val >= 0:
                            rate = delta_val / delta_t
                            fields += f",rate={rate:.6f}"

                    prev_values[label_key] = sample.value
                    prev_ts[label_key] = sample.timestamp.timestamp()
                else:
                    fields = f"value={sample.value:.6f}"

                line = f"{measurement}{tag_str} {fields} {ts_ns}"
                records.append(line)

                # Flush batch
                if len(records) >= WRITE_BATCH_SIZE:
                    self._flush(records)
                    records.clear()

        if records:
            self._flush(records)

    def _flush(self, records: list[str]) -> None:
        self._write_api.write(
            bucket=self.bucket,
            org=self.org,
            record=records,
            write_precision=WritePrecision.NANOSECONDS,
        )

    @staticmethod
    def _format_tags(labels: dict[str, str]) -> str:
        if not labels:
            return " "
        # Tags must not contain spaces; sort for consistent ordering
        parts = [f"{k}={v.replace(' ', '_')}" for k, v in sorted(labels.items())]
        return "," + ",".join(parts) + " "

    def ensure_dbrp_mapping(self) -> None:
        """Create a DBRP mapping so InfluxQL queries work against the v2 bucket.

        The InfluxQL compatibility endpoint requires a database→bucket mapping.
        This is idempotent — if the mapping already exists, InfluxDB returns 201
        or a conflict that we ignore.
        """
        # Look up the bucket ID first
        buckets_api = self._client.buckets_api()
        bucket = buckets_api.find_bucket_by_name(self.bucket)
        if bucket is None:
            return

        payload = json.dumps(
            {
                "bucketID": bucket.id,
                "database": self.bucket,
                "default": True,
                "org": self.org,
                "retention_policy": "autogen",
            }
        ).encode()

        req = urllib.request.Request(
            f"{self.url}/api/v2/dbrps",
            data=payload,
            headers={
                "Authorization": f"Token {self.token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            urllib.request.urlopen(req)
        except urllib.error.HTTPError as exc:
            # 422 = mapping already exists — safe to ignore
            if exc.code != 422:
                raise

    def close(self) -> None:
        self._write_api.close()
        self._client.close()
