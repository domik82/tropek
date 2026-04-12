# SLO Test Data Generator Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the broken per-sample Python generator with a pandas-based three-layer architecture (Scenario → Shaper → Adapter) supporting Prometheus, InfluxDB, TimescaleDB, and CSV backends.

**Architecture:** Scenarios yield chunked profile DataFrames (abstract "what happened"). Shapers transform profiles into backend-specific metric DataFrames (resolution, labels, counter style). Adapters handle pure I/O. CSV input is just another scenario.

**Tech Stack:** Python 3.13, pandas, numpy, click, rich, influxdb-client, psycopg3, Docker Compose

**Spec:** `docs/superpowers/specs/2026-03-20-generator-refactor-design.md`

**Base path:** `observability_stack/integration-test/` (abbreviated as `$BASE` in commands)

**Path convention:** All file paths in the File Map are relative to the repo root.
All shell commands use `$BASE` as shorthand for `observability_stack/integration-test`.
Per project CLAUDE.md: no `cd && cmd` chains — use `uv run --directory` or `git -C` instead.

```bash
# Set once at session start:
BASE=observability_stack/integration-test
GEN=$BASE/generator
```

---

## File Map

### New Files (src layout)

```
generator/
├── pyproject.toml                          # uv project, optional extras [influxdb], [timescaledb]
├── Dockerfile                              # rewritten: uv install, promtool
│
├── src/slo_generator/
│   ├── __init__.py                         # version
│   ├── cli.py                              # Click CLI with subcommands
│   ├── pipeline.py                         # Pipeline wiring: scenario → shaper → adapter
│   ├── constants.py                        # SERVICES, HOSTS, DURATION_BUCKETS, profile schema
│   │
│   ├── scenarios/
│   │   ├── __init__.py                     # get_scenario() factory
│   │   ├── base.py                         # BaseScenario ABC, chunked timestamp generation
│   │   ├── healthy.py                      # HealthyScenario
│   │   ├── outage.py                       # OutageScenario
│   │   ├── degradation.py                  # DegradationScenario
│   │   └── csv_input.py                    # CSVScenario
│   │
│   ├── shapers/
│   │   ├── __init__.py                     # get_shaper() factory
│   │   ├── base.py                         # BaseShaper ABC
│   │   ├── prometheus.py                   # PrometheusShaper (downsample, cumulative, instance/job)
│   │   ├── influxdb.py                     # InfluxDBShaper (1s, delta+rate)
│   │   ├── timescaledb.py                  # TimescaleDBShaper (delta, summary histograms)
│   │   └── raw.py                          # RawShaper (passthrough)
│   │
│   └── adapters/
│       ├── __init__.py                     # get_adapter() factory
│       ├── base.py                         # BaseAdapter ABC
│       ├── prometheus.py                   # OpenMetrics file writer + promtool runner
│       ├── influxdb.py                     # Line protocol batch writer + DBRP
│       ├── timescaledb.py                  # psycopg COPY writer + hypertable DDL
│       └── csv.py                          # df.to_csv() writer
│
├── tests/
│   ├── conftest.py                         # shared fixtures (sample profile chunks, timestamps)
│   ├── test_scenarios.py                   # scenario output shape, value ranges, chunking
│   ├── test_shapers.py                     # shaper output schema, counter monotonicity, resolution
│   ├── test_adapters.py                    # adapter I/O (file content, format correctness)
│   ├── test_pipeline.py                    # end-to-end: scenario → shaper → adapter
│   └── test_csv_input.py                   # CSV validation, roundtrip
```

### Deleted Files

```
generator/models.py                         # replaced by pandas DataFrames
generator/requirements.txt                  # replaced by pyproject.toml
generator/main.py                           # replaced by src/slo_generator/cli.py
generator/scenarios/base.py                 # rewritten
generator/scenarios/healthy.py              # rewritten
generator/scenarios/outage.py               # rewritten
generator/scenarios/degradation.py          # rewritten
generator/adapters/base.py                  # rewritten
generator/adapters/prometheus_adapter.py    # rewritten
generator/adapters/influxdb_adapter.py      # rewritten
generator/adapters/csv_adapter.py           # rewritten
```

### Modified Files

```
docker-compose.yml                          # add timescaledb-metrics service, update generator
grafana/provisioning/datasources/all.yml    # add TimescaleDB datasource
grafana/dashboard_config.yaml               # add influxql + sql queries per panel
grafana/generate_dashboard.py               # render 3 dashboards from config
grafana/templates/dashboard.json.j2         # parameterize datasource
Makefile                                    # update commands
CLAUDE.md                                   # update file map and commands
```

---

## Task 1: Project Scaffolding + Constants

**Files:**
- Create: `generator/pyproject.toml`
- Create: `generator/src/slo_generator/__init__.py`
- Create: `generator/src/slo_generator/constants.py`
- Create: `generator/tests/conftest.py`
- Delete: `generator/models.py`
- Delete: `generator/requirements.txt`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "slo-generator"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "pandas>=2.2",
    "numpy>=1.26",
    "click>=8.1",
    "rich>=13.7",
]

[project.optional-dependencies]
influxdb = ["influxdb-client>=1.41"]
timescaledb = ["psycopg[binary]>=3.1"]
all = ["slo-generator[influxdb,timescaledb]"]

[project.scripts]
slo-generate = "slo_generator.cli:main"

[tool.pytest.ini_options]
testpaths = ["tests"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

- [ ] **Step 2: Create `src/slo_generator/__init__.py`**

```python
"""SLO Test Data Generator."""
```

- [ ] **Step 3: Create `src/slo_generator/constants.py`**

Define all shared constants: services, hosts, histogram buckets, profile DataFrame column schema.

```python
"""Shared constants for the SLO test data generator."""

from __future__ import annotations

SERVICES: list[str] = ["frontend", "api", "backend"]
HOSTS: list[str] = ["host1", "host2"]

# Standard Prometheus histogram buckets for request durations (seconds)
DURATION_BUCKETS: list[float] = [
    0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0,
]

# Profile DataFrame columns — every scenario must produce exactly these
PROFILE_COLUMNS: list[str] = [
    "timestamp",
    "service",
    "host",
    "throughput_rps",
    "error_rate",
    "p50_latency",
    "p99_latency",
    "cpu_percent",
    "memory_bytes",
]

# Healthy baseline values (used as defaults across scenarios)
HEALTHY_DEFAULTS: dict[str, float] = {
    "throughput_rps": 100.0,
    "error_rate": 0.001,
    "p50_latency": 0.020,
    "p99_latency": 0.080,
    "cpu_percent": 40.0,
    "memory_bytes": 512 * 1024 * 1024,
}

# Per-service throughput scaling factors
SERVICE_FACTORS: dict[str, float] = {
    "frontend": 1.2,
    "api": 1.0,
    "backend": 0.8,
}

# Per-host scaling factors
HOST_FACTORS: dict[str, float] = {
    "host1": 1.05,
    "host2": 0.95,
}
```

- [ ] **Step 4: Create `tests/conftest.py`**

```python
"""Shared test fixtures for the SLO generator."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from slo_generator.constants import PROFILE_COLUMNS


@pytest.fixture
def sample_timestamps() -> list[datetime]:
    """One hour of timestamps at 1s resolution."""
    base = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
    return [base + pd.Timedelta(seconds=i) for i in range(3600)]


@pytest.fixture
def sample_profile_chunk() -> pd.DataFrame:
    """A small profile DataFrame (60 seconds, 1 service, 1 host) for unit tests."""
    base = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
    timestamps = [base + pd.Timedelta(seconds=i) for i in range(60)]
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(timestamps, utc=True),
            "service": pd.Categorical(["frontend"] * 60),
            "host": pd.Categorical(["host1"] * 60),
            "throughput_rps": [100.0] * 60,
            "error_rate": [0.001] * 60,
            "p50_latency": [0.020] * 60,
            "p99_latency": [0.080] * 60,
            "cpu_percent": [40.0] * 60,
            "memory_bytes": [512 * 1024 * 1024] * 60,
        }
    )


def validate_profile_schema(df: pd.DataFrame) -> None:
    """Assert a DataFrame matches the profile schema."""
    assert list(df.columns) == PROFILE_COLUMNS
    assert df["timestamp"].dtype == "datetime64[ns, UTC]"
    assert df["service"].dtype.name == "category"
    assert df["host"].dtype.name == "category"
```

- [ ] **Step 5: Delete old files**

```bash
rm $GEN/models.py $GEN/requirements.txt
```

- [ ] **Step 6: Install and verify**

Run: `uv sync --directory $GEN`
Expected: dependencies install, `slo_generator` package is importable.

- [ ] **Step 7: Commit**

```bash
git add $GEN/pyproject.toml generator/src/ generator/tests/conftest.py
git rm $GEN/models.py $GEN/requirements.txt
git commit -m "refactor: scaffold slo-generator package with constants and test fixtures"
```

---

## Task 2: BaseScenario + HealthyScenario

**Files:**
- Create: `generator/src/slo_generator/scenarios/__init__.py`
- Create: `generator/src/slo_generator/scenarios/base.py`
- Create: `generator/src/slo_generator/scenarios/healthy.py`
- Create: `generator/tests/test_scenarios.py`

- [ ] **Step 1: Write failing tests for BaseScenario + HealthyScenario**

```python
"""Tests for scenario profile generation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from tests.conftest import validate_profile_schema


class TestHealthyScenario:
    def test_generates_profile_dataframe_with_correct_schema(self):
        from slo_generator.scenarios.healthy import HealthyScenario

        start = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        end = start + timedelta(hours=1)
        scenario = HealthyScenario(start, end)

        chunks = list(scenario.generate(resolution_seconds=1))
        assert len(chunks) == 1  # 1 hour = 1 chunk
        df = chunks[0]
        validate_profile_schema(df)

    def test_produces_rows_for_all_service_host_combos(self):
        from slo_generator.scenarios.healthy import HealthyScenario

        start = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        end = start + timedelta(minutes=1)
        scenario = HealthyScenario(start, end)

        chunks = list(scenario.generate(resolution_seconds=1))
        df = pd.concat(chunks)

        services = set(df["service"].unique())
        hosts = set(df["host"].unique())
        assert services == {"frontend", "api", "backend"}
        assert hosts == {"host1", "host2"}

    def test_throughput_has_diurnal_variation(self):
        from slo_generator.scenarios.healthy import HealthyScenario

        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=timezone.utc)
        end = start + timedelta(hours=24)
        scenario = HealthyScenario(start, end)

        chunks = list(scenario.generate(resolution_seconds=60))
        df = pd.concat(chunks)

        # Filter to one service-host combo
        mask = (df["service"] == "api") & (df["host"] == "host1")
        series = df.loc[mask, "throughput_rps"]

        # Should vary by ~±15%, not flat
        assert series.std() > 1.0  # not a flat line
        assert series.min() > 50.0  # reasonable lower bound
        assert series.max() < 200.0  # reasonable upper bound

    def test_values_within_healthy_bounds(self):
        from slo_generator.scenarios.healthy import HealthyScenario

        start = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        end = start + timedelta(minutes=10)
        scenario = HealthyScenario(start, end)

        chunks = list(scenario.generate(resolution_seconds=1))
        df = pd.concat(chunks)

        assert (df["error_rate"] >= 0).all()
        assert (df["error_rate"] < 0.01).all()
        assert (df["cpu_percent"] >= 0).all()
        assert (df["cpu_percent"] <= 100).all()
        assert (df["p99_latency"] > 0).all()
        assert (df["p99_latency"] < 1.0).all()

    def test_chunked_output_bounds_memory(self):
        from slo_generator.scenarios.healthy import HealthyScenario

        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=timezone.utc)
        end = start + timedelta(hours=3)
        scenario = HealthyScenario(start, end)

        chunks = list(scenario.generate(resolution_seconds=1))
        # 3 hours should produce 3 chunks (1 per hour)
        assert len(chunks) == 3

        # Each chunk should have roughly 1 hour of data
        for chunk in chunks:
            duration = chunk["timestamp"].max() - chunk["timestamp"].min()
            assert duration <= pd.Timedelta(hours=1)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory $GEN pytest tests/test_scenarios.py -v`
Expected: ImportError — `slo_generator.scenarios.healthy` not found.

- [ ] **Step 3: Implement `scenarios/__init__.py`**

```python
"""Scenario factory."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from slo_generator.scenarios.base import BaseScenario


def get_scenario(name: str, **kwargs) -> BaseScenario:
    """Factory for creating scenarios by name."""
    from slo_generator.scenarios.csv_input import CSVScenario
    from slo_generator.scenarios.degradation import DegradationScenario
    from slo_generator.scenarios.healthy import HealthyScenario
    from slo_generator.scenarios.outage import OutageScenario

    scenarios = {
        "healthy": HealthyScenario,
        "outage": OutageScenario,
        "degradation": DegradationScenario,
        "csv": CSVScenario,
    }
    if name not in scenarios:
        raise ValueError(f"unknown scenario: {name!r}, expected one of {list(scenarios)}")
    return scenarios[name](**kwargs)
```

- [ ] **Step 4: Implement `scenarios/base.py`**

BaseScenario ABC with chunked timestamp generation. Subclasses implement `_build_profiles()` which returns a full-resolution DataFrame for a time range. Base class handles chunking.

```python
"""Base scenario — defines the interface all scenarios implement."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Iterator

import numpy as np
import pandas as pd

from slo_generator.constants import HOSTS, PROFILE_COLUMNS, SERVICES


class BaseScenario(ABC):
    """Abstract base for all data generation scenarios."""

    name: str = "base"

    def __init__(self, start: datetime, end: datetime):
        self.start = start
        self.end = end
        self._rng = np.random.default_rng(seed=42)

    def generate(
        self,
        resolution_seconds: int = 1,
        chunk_hours: int = 1,
    ) -> Iterator[pd.DataFrame]:
        """Yield profile DataFrames in hour-sized chunks."""
        chunk_delta = timedelta(hours=chunk_hours)
        chunk_start = self.start

        while chunk_start < self.end:
            chunk_end = min(chunk_start + chunk_delta, self.end)
            timestamps = pd.date_range(
                chunk_start, chunk_end, freq=f"{resolution_seconds}s", inclusive="left", tz="UTC",
            )
            if len(timestamps) == 0:
                chunk_start = chunk_end
                continue

            df = self._build_chunk(timestamps)
            yield df
            chunk_start = chunk_end

    def _build_chunk(self, timestamps: pd.DatetimeIndex) -> pd.DataFrame:
        """Build a profile DataFrame for one chunk by combining all service-host combos."""
        frames: list[pd.DataFrame] = []
        for service in SERVICES:
            for host in HOSTS:
                profiles = self._build_profiles(timestamps, service, host)
                profiles["service"] = pd.Categorical([service] * len(timestamps), categories=SERVICES)
                profiles["host"] = pd.Categorical([host] * len(timestamps), categories=HOSTS)
                frames.append(profiles)

        df = pd.concat(frames, ignore_index=True)
        return df[PROFILE_COLUMNS]

    @abstractmethod
    def _build_profiles(
        self, timestamps: pd.DatetimeIndex, service: str, host: str,
    ) -> pd.DataFrame:
        """Build profile values for one (service, host) across all timestamps in chunk.

        Must return a DataFrame with columns: timestamp, throughput_rps, error_rate,
        p50_latency, p99_latency, cpu_percent, memory_bytes.
        (service and host are added by the base class.)
        """
        ...
```

- [ ] **Step 5: Implement `scenarios/healthy.py`**

Vectorized diurnal variation using numpy operations on the timestamp array.

```python
"""Healthy scenario — everything is normal, mild diurnal variation."""

from __future__ import annotations

import numpy as np
import pandas as pd

from slo_generator.constants import HEALTHY_DEFAULTS, HOST_FACTORS, SERVICE_FACTORS
from slo_generator.scenarios.base import BaseScenario


class HealthyScenario(BaseScenario):
    """Simulates a healthy system with mild diurnal variation (~±15%)."""

    name = "healthy"

    def _build_profiles(
        self, timestamps: pd.DatetimeIndex, service: str, host: str,
    ) -> pd.DataFrame:
        n = len(timestamps)
        hours = timestamps.hour + timestamps.minute / 60
        diurnal = 1.0 + 0.15 * np.sin(2 * np.pi * (hours / 24 - 0.25))

        sf = SERVICE_FACTORS.get(service, 1.0)
        hf = HOST_FACTORS.get(host, 1.0)

        base_throughput = HEALTHY_DEFAULTS["throughput_rps"] * sf * hf
        throughput = np.maximum(10.0, base_throughput * diurnal)

        cpu_base = HEALTHY_DEFAULTS["cpu_percent"]
        cpu = np.clip(
            cpu_base * (0.8 + 0.4 * (throughput / (HEALTHY_DEFAULTS["throughput_rps"] * sf))),
            0.0,
            100.0,
        )

        return pd.DataFrame(
            {
                "timestamp": timestamps,
                "throughput_rps": throughput,
                "error_rate": np.full(n, HEALTHY_DEFAULTS["error_rate"]),
                "p50_latency": np.full(n, HEALTHY_DEFAULTS["p50_latency"]),
                "p99_latency": np.full(n, HEALTHY_DEFAULTS["p99_latency"]),
                "cpu_percent": cpu,
                "memory_bytes": np.full(n, HEALTHY_DEFAULTS["memory_bytes"] * hf),
            }
        )
```

- [ ] **Step 6: Run tests**

Run: `uv run --directory $GEN pytest tests/test_scenarios.py -v`
Expected: All 5 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add $GEN/src/slo_generator/scenarios/
git add $GEN/tests/test_scenarios.py
git commit -m "feat: add BaseScenario + HealthyScenario with chunked pandas generation"
```

---

## Task 3: OutageScenario + DegradationScenario

**Files:**
- Create: `generator/src/slo_generator/scenarios/outage.py`
- Create: `generator/src/slo_generator/scenarios/degradation.py`
- Modify: `generator/tests/test_scenarios.py`

- [ ] **Step 1: Write failing tests for OutageScenario**

Add to `tests/test_scenarios.py`:

```python
class TestOutageScenario:
    def test_throughput_drops_during_outage(self):
        from slo_generator.scenarios.outage import OutageScenario

        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=timezone.utc)
        end = start + timedelta(hours=12)
        scenario = OutageScenario(start, end, outage_duration_minutes=30)

        chunks = list(scenario.generate(resolution_seconds=30))
        df = pd.concat(chunks)
        api = df[(df["service"] == "api") & (df["host"] == "host1")]

        # Pre-outage throughput should be healthy (~100 rps)
        pre = api[api["timestamp"] < start + timedelta(hours=6)]
        assert pre["throughput_rps"].mean() > 80

        # During outage throughput should be collapsed
        outage_start = start + timedelta(seconds=12 * 3600 * 0.60)
        outage_end = outage_start + timedelta(minutes=30)
        during = api[(api["timestamp"] >= outage_start + timedelta(minutes=5)) & (api["timestamp"] < outage_end)]
        if len(during) > 0:
            assert during["throughput_rps"].mean() < 20

    def test_error_rate_spikes_during_outage(self):
        from slo_generator.scenarios.outage import OutageScenario

        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=timezone.utc)
        end = start + timedelta(hours=12)
        scenario = OutageScenario(start, end, outage_duration_minutes=30)

        chunks = list(scenario.generate(resolution_seconds=30))
        df = pd.concat(chunks)
        api = df[(df["service"] == "api") & (df["host"] == "host1")]

        outage_start = start + timedelta(seconds=12 * 3600 * 0.60)
        outage_end = outage_start + timedelta(minutes=30)
        during = api[(api["timestamp"] >= outage_start + timedelta(minutes=5)) & (api["timestamp"] < outage_end)]
        if len(during) > 0:
            assert during["error_rate"].mean() > 0.5
```

- [ ] **Step 2: Write failing tests for DegradationScenario**

Add to `tests/test_scenarios.py`:

```python
class TestDegradationScenario:
    def test_throughput_unchanged_during_degradation(self):
        from slo_generator.scenarios.degradation import DegradationScenario

        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=timezone.utc)
        end = start + timedelta(hours=12)
        scenario = DegradationScenario(start, end)

        chunks = list(scenario.generate(resolution_seconds=30))
        df = pd.concat(chunks)
        api = df[(df["service"] == "api") & (df["host"] == "host1")]

        pre = api[api["timestamp"] < start + timedelta(hours=6)]
        post = api[api["timestamp"] > start + timedelta(hours=10)]

        # Throughput should be roughly the same pre and post deploy
        assert abs(pre["throughput_rps"].mean() - post["throughput_rps"].mean()) < 20

    def test_latency_increases_during_degradation(self):
        from slo_generator.scenarios.degradation import DegradationScenario

        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=timezone.utc)
        end = start + timedelta(hours=12)
        scenario = DegradationScenario(start, end)

        chunks = list(scenario.generate(resolution_seconds=30))
        df = pd.concat(chunks)
        api = df[(df["service"] == "api") & (df["host"] == "host1")]

        pre = api[api["timestamp"] < start + timedelta(hours=6)]
        post = api[api["timestamp"] > start + timedelta(hours=10)]

        # P99 should be roughly 5x higher after deployment
        assert post["p99_latency"].mean() > pre["p99_latency"].mean() * 3
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run --directory $GEN pytest tests/test_scenarios.py -v -k "Outage or Degradation"`
Expected: ImportError.

- [ ] **Step 4: Implement `scenarios/outage.py`**

Port the outage math (three phases: healthy → ramp → recovery) to vectorized pandas.

```python
"""Outage scenario — sudden failure affecting all services."""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from slo_generator.constants import HEALTHY_DEFAULTS, SERVICE_FACTORS
from slo_generator.scenarios.base import BaseScenario


class OutageScenario(BaseScenario):
    """Simulates a full outage: high errors, low throughput, high latency."""

    name = "outage"

    def __init__(
        self,
        start: datetime,
        end: datetime,
        outage_duration_minutes: int = 30,
        recovery_minutes: int = 10,
    ):
        super().__init__(start, end)
        total = (end - start).total_seconds()
        self.outage_start = start + timedelta(seconds=total * 0.60)
        self.outage_end = self.outage_start + timedelta(minutes=outage_duration_minutes)
        self.recovery_end = self.outage_end + timedelta(minutes=recovery_minutes)

    def _build_profiles(
        self, timestamps: pd.DatetimeIndex, service: str, host: str,
    ) -> pd.DataFrame:
        n = len(timestamps)
        sf = SERVICE_FACTORS.get(service, 1.0)
        base = HEALTHY_DEFAULTS

        ts_epoch = timestamps.astype(np.int64) / 1e9
        outage_start_epoch = self.outage_start.timestamp()
        outage_end_epoch = self.outage_end.timestamp()
        recovery_end_epoch = self.recovery_end.timestamp()

        # Phase masks
        pre = ts_epoch < outage_start_epoch
        outage = (ts_epoch >= outage_start_epoch) & (ts_epoch < outage_end_epoch)
        recovery = (ts_epoch >= outage_end_epoch) & (ts_epoch < recovery_end_epoch)
        post = ts_epoch >= recovery_end_epoch

        # Ramp fraction during outage (0→1 over 2 minutes)
        ramp = np.clip((ts_epoch - outage_start_epoch) / 120.0, 0.0, 1.0)

        # Recovery fraction (0→1 over recovery window)
        rec_duration = (self.recovery_end - self.outage_end).total_seconds()
        rec_frac = np.clip((ts_epoch - outage_end_epoch) / rec_duration, 0.0, 1.0)

        throughput = np.where(
            pre, base["throughput_rps"] * sf,
            np.where(outage, np.maximum(2.0, base["throughput_rps"] * sf * (1 - ramp * 0.90)),
            np.where(recovery, np.maximum(10.0, 2.0 + rec_frac * (base["throughput_rps"] * sf - 2.0)),
            base["throughput_rps"] * sf)))

        error_rate = np.where(
            pre, base["error_rate"],
            np.where(outage, np.minimum(0.95, base["error_rate"] + ramp * 0.79),
            np.where(recovery, np.maximum(base["error_rate"], 0.95 - rec_frac * (0.95 - base["error_rate"])),
            base["error_rate"])))

        p99 = np.where(
            pre, base["p99_latency"],
            np.where(outage, base["p99_latency"] + ramp * 9.92,
            np.where(recovery, np.maximum(base["p99_latency"], 10.0 - rec_frac * (10.0 - base["p99_latency"])),
            base["p99_latency"])))

        p50 = np.where(
            pre, base["p50_latency"],
            np.where(outage, base["p50_latency"] * (1 + ramp * 5),
            np.where(recovery, np.maximum(base["p50_latency"], base["p50_latency"] * (1 + (1 - rec_frac) * 5)),
            base["p50_latency"])))

        cpu = np.where(
            pre, base["cpu_percent"],
            np.where(outage, np.minimum(95.0, base["cpu_percent"] + ramp * 50),
            np.where(recovery, np.minimum(100.0, 95.0 - rec_frac * (95.0 - base["cpu_percent"])),
            base["cpu_percent"])))

        return pd.DataFrame({
            "timestamp": timestamps,
            "throughput_rps": throughput,
            "error_rate": error_rate,
            "p50_latency": p50,
            "p99_latency": p99,
            "cpu_percent": cpu,
            "memory_bytes": np.full(n, base["memory_bytes"]),
        })
```

- [ ] **Step 5: Implement `scenarios/degradation.py`**

Port the degradation math (two phases: healthy → sustained regression) to vectorized pandas.

```python
"""Degradation scenario — deployment regression with visible latency increase."""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from slo_generator.constants import HEALTHY_DEFAULTS, SERVICE_FACTORS
from slo_generator.scenarios.base import BaseScenario


class DegradationScenario(BaseScenario):
    """Simulates a bad deployment: latency 5×, error rate 5×, throughput unchanged."""

    name = "degradation"

    def __init__(
        self,
        start: datetime,
        end: datetime,
        ramp_minutes: int = 5,
        latency_multiplier: float = 5.0,
        error_rate_multiplier: float = 5.0,
    ):
        super().__init__(start, end)
        total = (end - start).total_seconds()
        self.deploy_start = start + timedelta(seconds=total * 0.65)
        self.ramp_end = self.deploy_start + timedelta(minutes=ramp_minutes)
        self.lat_mult = latency_multiplier
        self.err_mult = error_rate_multiplier

    def _build_profiles(
        self, timestamps: pd.DatetimeIndex, service: str, host: str,
    ) -> pd.DataFrame:
        n = len(timestamps)
        sf = SERVICE_FACTORS.get(service, 1.0)
        base = HEALTHY_DEFAULTS

        ts_epoch = timestamps.astype(np.int64) / 1e9
        deploy_epoch = self.deploy_start.timestamp()
        ramp_end_epoch = self.ramp_end.timestamp()
        ramp_duration = (self.ramp_end - self.deploy_start).total_seconds()

        pre = ts_epoch < deploy_epoch
        ramp = (ts_epoch >= deploy_epoch) & (ts_epoch < ramp_end_epoch)
        degraded = ts_epoch >= ramp_end_epoch

        ramp_frac = np.clip((ts_epoch - deploy_epoch) / ramp_duration, 0.0, 1.0)

        p99 = np.where(
            pre, base["p99_latency"],
            np.where(ramp, base["p99_latency"] * (1 + ramp_frac * (self.lat_mult - 1)),
            base["p99_latency"] * self.lat_mult))

        p50 = np.where(
            pre, base["p50_latency"],
            np.where(ramp, np.maximum(base["p50_latency"], base["p50_latency"] * (1 + ramp_frac * (self.lat_mult * 0.5 - 1))),
            base["p50_latency"] * self.lat_mult * 0.5))

        error_rate = np.where(
            pre, base["error_rate"],
            np.where(ramp, base["error_rate"] * (1 + ramp_frac * (self.err_mult - 1)),
            base["error_rate"] * self.err_mult))

        cpu = np.where(
            pre, base["cpu_percent"],
            np.where(ramp, np.minimum(100.0, base["cpu_percent"] * (1 + ramp_frac * 0.35)),
            np.minimum(100.0, base["cpu_percent"] * 1.35)))

        return pd.DataFrame({
            "timestamp": timestamps,
            "throughput_rps": np.full(n, base["throughput_rps"] * sf),
            "error_rate": error_rate,
            "p50_latency": p50,
            "p99_latency": p99,
            "cpu_percent": cpu,
            "memory_bytes": np.full(n, base["memory_bytes"]),
        })
```

- [ ] **Step 6: Run tests**

Run: `uv run --directory $GEN pytest tests/test_scenarios.py -v`
Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add $GEN/src/slo_generator/scenarios/outage.py generator/src/slo_generator/scenarios/degradation.py
git add $GEN/tests/test_scenarios.py
git commit -m "feat: add OutageScenario + DegradationScenario (vectorized pandas)"
```

---

## Task 4: CSVScenario

**Files:**
- Create: `generator/src/slo_generator/scenarios/csv_input.py`
- Create: `generator/tests/test_csv_input.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for CSV input scenario."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from tests.conftest import validate_profile_schema


@pytest.fixture
def csv_file(tmp_path: Path) -> Path:
    """Create a valid CSV file with 60 seconds of data."""
    base = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
    rows = []
    for i in range(60):
        ts = base + timedelta(seconds=i)
        rows.append({
            "timestamp": ts.isoformat(),
            "service": "frontend",
            "host": "host1",
            "throughput_rps": 100.0 + i,  # ramp
            "error_rate": 0.001,
            "p50_latency": 0.020,
            "p99_latency": 0.080,
            "cpu_percent": 40.0,
            "memory_bytes": 536870912,
        })
    df = pd.DataFrame(rows)
    path = tmp_path / "input.csv"
    df.to_csv(path, index=False)
    return path


class TestCSVScenario:
    def test_loads_and_yields_profile_dataframe(self, csv_file: Path):
        from slo_generator.scenarios.csv_input import CSVScenario

        scenario = CSVScenario(csv_file)
        chunks = list(scenario.generate())
        assert len(chunks) >= 1
        df = pd.concat(chunks)
        validate_profile_schema(df)
        assert len(df) == 60

    def test_preserves_values_from_csv(self, csv_file: Path):
        from slo_generator.scenarios.csv_input import CSVScenario

        scenario = CSVScenario(csv_file)
        df = pd.concat(scenario.generate())
        # First row should have throughput 100.0, last row 159.0
        assert df.iloc[0]["throughput_rps"] == pytest.approx(100.0)
        assert df.iloc[-1]["throughput_rps"] == pytest.approx(159.0)

    def test_rejects_missing_columns(self, tmp_path: Path):
        from slo_generator.scenarios.csv_input import CSVScenario

        path = tmp_path / "bad.csv"
        pd.DataFrame({"timestamp": ["2026-01-01"], "service": ["x"]}).to_csv(path, index=False)

        with pytest.raises(ValueError, match="missing columns"):
            CSVScenario(path)

    def test_roundtrip_with_raw_shaper(self, csv_file: Path):
        """CSV in → RawShaper out should produce the same data."""
        from slo_generator.scenarios.csv_input import CSVScenario

        scenario = CSVScenario(csv_file)
        df = pd.concat(scenario.generate())
        assert len(df) == 60
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory $GEN pytest tests/test_csv_input.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `scenarios/csv_input.py`**

```python
"""CSV input scenario — reads a user-provided CSV as a profile DataFrame."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import pandas as pd

from slo_generator.constants import PROFILE_COLUMNS, SERVICES, HOSTS
from slo_generator.scenarios.base import BaseScenario


class CSVScenario:
    """Reads a CSV file and yields it as profile DataFrames.

    The CSV must contain all profile columns. Timestamps are parsed to UTC.
    Data is yielded in 1-hour chunks.
    """

    name = "csv"

    def __init__(self, csv_path: Path | str):
        self.csv_path = Path(csv_path)
        self._validate()

    def _validate(self) -> None:
        """Check that the CSV has the required columns."""
        df_head = pd.read_csv(self.csv_path, nrows=2)
        required = set(PROFILE_COLUMNS)
        actual = set(df_head.columns)
        missing = required - actual
        if missing:
            raise ValueError(f"missing columns in {self.csv_path.name}: {sorted(missing)}")

    def generate(self, resolution_seconds: int = 1) -> Iterator[pd.DataFrame]:
        """Read CSV in chunks and yield profile DataFrames."""
        for chunk in pd.read_csv(
            self.csv_path,
            parse_dates=["timestamp"],
            chunksize=21_600,  # ~1 hour at 1s with 6 service-host combos
        ):
            chunk["timestamp"] = pd.to_datetime(chunk["timestamp"], utc=True)
            chunk["service"] = pd.Categorical(chunk["service"], categories=SERVICES)
            chunk["host"] = pd.Categorical(chunk["host"], categories=HOSTS)
            yield chunk[PROFILE_COLUMNS]
```

- [ ] **Step 4: Run tests**

Run: `uv run --directory $GEN pytest tests/test_csv_input.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add $GEN/src/slo_generator/scenarios/csv_input.py generator/tests/test_csv_input.py
git commit -m "feat: add CSVScenario for hand-crafted edge-case inputs"
```

---

## Task 5: RawShaper + BaseShaper

**Files:**
- Create: `generator/src/slo_generator/shapers/__init__.py`
- Create: `generator/src/slo_generator/shapers/base.py`
- Create: `generator/src/slo_generator/shapers/raw.py`
- Create: `generator/tests/test_shapers.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for metric shapers."""

from __future__ import annotations

import pandas as pd
import pytest


class TestRawShaper:
    def test_passthrough_returns_same_data(self, sample_profile_chunk: pd.DataFrame):
        from slo_generator.shapers.raw import RawShaper

        shaper = RawShaper()
        shaped = list(shaper.shape(sample_profile_chunk))
        assert len(shaped) == 1
        pd.testing.assert_frame_equal(shaped[0], sample_profile_chunk)

    def test_finalize_yields_nothing(self):
        from slo_generator.shapers.raw import RawShaper

        shaper = RawShaper()
        assert list(shaper.finalize()) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory $GEN pytest tests/test_shapers.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `shapers/base.py`**

```python
"""Base shaper interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator

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
```

- [ ] **Step 4: Implement `shapers/raw.py`**

```python
"""Raw shaper — passthrough for CSV output."""

from __future__ import annotations

from typing import Iterator

import pandas as pd

from slo_generator.shapers.base import BaseShaper


class RawShaper(BaseShaper):
    """Passes profile DataFrame through unchanged."""

    def shape(self, profile_chunk: pd.DataFrame) -> Iterator[pd.DataFrame]:
        yield profile_chunk
```

- [ ] **Step 5: Implement `shapers/__init__.py`**

```python
"""Shaper factory."""

from __future__ import annotations

from typing import Any

from slo_generator.shapers.base import BaseShaper


def get_shaper(backend: str, **config: Any) -> BaseShaper:
    """Factory for creating shapers by backend name."""
    from slo_generator.shapers.influxdb import InfluxDBShaper
    from slo_generator.shapers.prometheus import PrometheusShaper
    from slo_generator.shapers.raw import RawShaper
    from slo_generator.shapers.timescaledb import TimescaleDBShaper

    shapers: dict[str, type[BaseShaper]] = {
        "prometheus": PrometheusShaper,
        "influxdb": InfluxDBShaper,
        "timescaledb": TimescaleDBShaper,
        "csv": RawShaper,
    }
    if backend not in shapers:
        raise ValueError(f"unknown backend: {backend!r}, expected one of {list(shapers)}")
    return shapers[backend](**config)
```

- [ ] **Step 6: Run tests**

Run: `uv run --directory $GEN pytest tests/test_shapers.py -v`
Expected: All PASS.

- [ ] **Step 7: Commit**

```bash
git add $GEN/src/slo_generator/shapers/
git add $GEN/tests/test_shapers.py
git commit -m "feat: add BaseShaper + RawShaper (passthrough)"
```

---

## Task 6: PrometheusShaper

**Files:**
- Create: `generator/src/slo_generator/shapers/prometheus.py`
- Modify: `generator/tests/test_shapers.py`

This is the most complex shaper — handles downsampling, cumulative counters, histogram expansion, and Prometheus-specific labels.

- [ ] **Step 1: Write failing tests**

Add to `tests/test_shapers.py`:

```python
class TestPrometheusShaper:
    def test_output_has_prometheus_columns(self, sample_profile_chunk: pd.DataFrame):
        from slo_generator.shapers.prometheus import PrometheusShaper

        shaper = PrometheusShaper(scrape_interval=30)
        shaped = list(shaper.shape(sample_profile_chunk))
        df = pd.concat(shaped)

        required = {"timestamp", "metric", "value", "service", "host", "instance", "job"}
        assert required.issubset(set(df.columns))

    def test_downsamples_to_scrape_interval(self, sample_profile_chunk: pd.DataFrame):
        from slo_generator.shapers.prometheus import PrometheusShaper

        shaper = PrometheusShaper(scrape_interval=30)
        shaped = list(shaper.shape(sample_profile_chunk))
        df = pd.concat(shaped)

        # 60s of 1s data downsampled to 30s → 2 timestamps per metric per label set
        ts_per_metric = df.groupby(["metric", "service", "host"])["timestamp"].nunique()
        assert (ts_per_metric == 2).all()

    def test_counter_values_are_monotonically_increasing(self, sample_profile_chunk: pd.DataFrame):
        from slo_generator.shapers.prometheus import PrometheusShaper

        shaper = PrometheusShaper(scrape_interval=30)
        shaped = list(shaper.shape(sample_profile_chunk))
        df = pd.concat(shaped)

        counters = df[df["metric"] == "http_requests_total"].sort_values("timestamp")
        for _, group in counters.groupby(["service", "host", "instance"]):
            values = group["value"].values
            assert all(values[i] <= values[i + 1] for i in range(len(values) - 1))

    def test_instance_and_job_labels_present(self, sample_profile_chunk: pd.DataFrame):
        from slo_generator.shapers.prometheus import PrometheusShaper

        shaper = PrometheusShaper(scrape_interval=30)
        shaped = list(shaper.shape(sample_profile_chunk))
        df = pd.concat(shaped)

        assert (df["job"] == "app").all()
        assert df["instance"].str.contains(":").all()  # format: service-host:port

    def test_histogram_buckets_present(self, sample_profile_chunk: pd.DataFrame):
        from slo_generator.shapers.prometheus import PrometheusShaper

        shaper = PrometheusShaper(scrape_interval=30)
        shaped = list(shaper.shape(sample_profile_chunk))
        df = pd.concat(shaped)

        buckets = df[df["metric"] == "http_request_duration_seconds_bucket"]
        assert len(buckets) > 0
        assert "+Inf" in buckets["le"].values

    def test_finalize_flushes_remaining_state(self, sample_profile_chunk: pd.DataFrame):
        from slo_generator.shapers.prometheus import PrometheusShaper

        shaper = PrometheusShaper(scrape_interval=30)
        # Feed data
        list(shaper.shape(sample_profile_chunk))
        # Finalize should not error
        final = list(shaper.finalize())
        # May or may not have data, but should not crash
        assert isinstance(final, list)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory $GEN pytest tests/test_shapers.py::TestPrometheusShaper -v`
Expected: ImportError.

- [ ] **Step 3: Implement `shapers/prometheus.py`**

The PrometheusShaper:
1. Downsamples profile to `scrape_interval` (default 30s)
2. For each downsampled row, expands into multiple metric rows:
   - `http_requests_total` — cumulative counter with `status_code=200`
   - `http_errors_total` — cumulative counter
   - `http_request_duration_seconds_bucket` — one row per `le` bucket, cumulative
   - `http_request_duration_seconds_sum` — cumulative
   - `http_request_duration_seconds_count` — cumulative
   - `cpu_usage_percent` — gauge (last value)
   - `memory_usage_bytes` — gauge (last value)
3. Adds `instance` and `job` labels
4. Maintains cumulative accumulators across chunks

Implementation should be ~120 lines. Key patterns:
- `df.groupby(pd.Grouper(key="timestamp", freq=f"{scrape_interval}s"))` for downsampling
- Counter deltas summed per window, then accumulated via `cumsum()`-like logic on the accumulator dict
- Histogram bucket fractions computed vectorized (same `_bucket_fraction` logic from original code)

- [ ] **Step 4: Run tests**

Run: `uv run --directory $GEN pytest tests/test_shapers.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add $GEN/src/slo_generator/shapers/prometheus.py generator/tests/test_shapers.py
git commit -m "feat: add PrometheusShaper with downsampling, cumulative counters, histograms"
```

---

## Task 7: InfluxDBShaper + TimescaleDBShaper

**Files:**
- Create: `generator/src/slo_generator/shapers/influxdb.py`
- Create: `generator/src/slo_generator/shapers/timescaledb.py`
- Modify: `generator/tests/test_shapers.py`

- [ ] **Step 1: Write failing tests for InfluxDBShaper**

Add to `tests/test_shapers.py`:

```python
class TestInfluxDBShaper:
    def test_output_has_influxdb_columns(self, sample_profile_chunk: pd.DataFrame):
        from slo_generator.shapers.influxdb import InfluxDBShaper

        shaper = InfluxDBShaper()
        shaped = list(shaper.shape(sample_profile_chunk))
        df = pd.concat(shaped)

        required = {"timestamp", "measurement", "service", "host", "value"}
        assert required.issubset(set(df.columns))

    def test_keeps_1s_resolution(self, sample_profile_chunk: pd.DataFrame):
        from slo_generator.shapers.influxdb import InfluxDBShaper

        shaper = InfluxDBShaper()
        shaped = list(shaper.shape(sample_profile_chunk))
        df = pd.concat(shaped)

        # Should preserve all 60 timestamps for each metric
        for _, grp in df.groupby(["measurement", "service", "host"]):
            ts = grp["timestamp"].unique()
            assert len(ts) == 60

    def test_counters_have_rate_field(self, sample_profile_chunk: pd.DataFrame):
        from slo_generator.shapers.influxdb import InfluxDBShaper

        shaper = InfluxDBShaper()
        shaped = list(shaper.shape(sample_profile_chunk))
        df = pd.concat(shaped)

        requests = df[df["measurement"] == "http_requests_total"]
        assert "rate" in requests.columns
        # Rate should be positive (throughput > 0)
        assert (requests["rate"].dropna() >= 0).all()
```

- [ ] **Step 2: Write failing tests for TimescaleDBShaper**

```python
class TestTimescaleDBShaper:
    def test_output_has_timescaledb_columns(self, sample_profile_chunk: pd.DataFrame):
        from slo_generator.shapers.timescaledb import TimescaleDBShaper

        shaper = TimescaleDBShaper()
        shaped = list(shaper.shape(sample_profile_chunk))
        df = pd.concat(shaped)

        required = {"timestamp", "metric", "service", "host", "value"}
        assert set(df.columns) == required

    def test_histograms_as_summary_rows(self, sample_profile_chunk: pd.DataFrame):
        from slo_generator.shapers.timescaledb import TimescaleDBShaper

        shaper = TimescaleDBShaper()
        shaped = list(shaper.shape(sample_profile_chunk))
        df = pd.concat(shaped)

        hist_metrics = df[df["metric"].str.startswith("http_request_duration")]
        metric_names = set(hist_metrics["metric"].unique())
        # Should have p50, p99, avg summary rows — not individual buckets
        assert "http_request_duration_seconds_p50" in metric_names
        assert "http_request_duration_seconds_p99" in metric_names
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run --directory $GEN pytest tests/test_shapers.py -v -k "InfluxDB or TimescaleDB"`
Expected: ImportError.

- [ ] **Step 4: Implement `shapers/influxdb.py`**

InfluxDB shaper: 1s resolution, delta values for counters, rate field, histogram bucket expansion.

- [ ] **Step 5: Implement `shapers/timescaledb.py`**

TimescaleDB shaper: 1s resolution, delta counters, histograms as p50/p99/avg summary rows.

- [ ] **Step 6: Run tests**

Run: `uv run --directory $GEN pytest tests/test_shapers.py -v`
Expected: All PASS.

- [ ] **Step 7: Commit**

```bash
git add $GEN/src/slo_generator/shapers/influxdb.py generator/src/slo_generator/shapers/timescaledb.py
git add $GEN/tests/test_shapers.py
git commit -m "feat: add InfluxDBShaper + TimescaleDBShaper"
```

---

## Task 8: CSVAdapter + BaseAdapter

**Files:**
- Create: `generator/src/slo_generator/adapters/__init__.py`
- Create: `generator/src/slo_generator/adapters/base.py`
- Create: `generator/src/slo_generator/adapters/csv.py`
- Create: `generator/tests/test_adapters.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for adapters (I/O layer)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


class TestCSVAdapter:
    def test_writes_dataframe_to_csv_file(self, tmp_path: Path, sample_profile_chunk: pd.DataFrame):
        from slo_generator.adapters.csv import CSVAdapter

        output = tmp_path / "output.csv"
        with CSVAdapter(output) as adapter:
            adapter.write_chunk(sample_profile_chunk)

        result = pd.read_csv(output)
        assert len(result) == len(sample_profile_chunk)
        assert set(result.columns) == set(sample_profile_chunk.columns)

    def test_appends_multiple_chunks(self, tmp_path: Path, sample_profile_chunk: pd.DataFrame):
        from slo_generator.adapters.csv import CSVAdapter

        output = tmp_path / "output.csv"
        with CSVAdapter(output) as adapter:
            adapter.write_chunk(sample_profile_chunk)
            adapter.write_chunk(sample_profile_chunk)

        result = pd.read_csv(output)
        assert len(result) == len(sample_profile_chunk) * 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory $GEN pytest tests/test_adapters.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `adapters/base.py`**

```python
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

    def close(self) -> None:
        """Flush and release resources."""

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
```

- [ ] **Step 4: Implement `adapters/csv.py`**

```python
"""CSV adapter — writes DataFrames to CSV files."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from slo_generator.adapters.base import BaseAdapter


class CSVAdapter(BaseAdapter):
    """Writes DataFrames to a CSV file, appending chunks."""

    def __init__(self, output_path: Path | str):
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._header_written = False

    def write_chunk(self, df: pd.DataFrame) -> None:
        df.to_csv(
            self.output_path,
            mode="a" if self._header_written else "w",
            header=not self._header_written,
            index=False,
        )
        self._header_written = True
```

- [ ] **Step 5: Implement `adapters/__init__.py`**

```python
"""Adapter factory."""

from __future__ import annotations

from typing import Any

from slo_generator.adapters.base import BaseAdapter


def get_adapter(backend: str, **config: Any) -> BaseAdapter:
    """Factory for creating adapters by backend name."""
    from slo_generator.adapters.csv import CSVAdapter
    from slo_generator.adapters.influxdb import InfluxDBAdapter
    from slo_generator.adapters.prometheus import PrometheusAdapter
    from slo_generator.adapters.timescaledb import TimescaleDBAdapter

    adapters: dict[str, type[BaseAdapter]] = {
        "prometheus": PrometheusAdapter,
        "influxdb": InfluxDBAdapter,
        "timescaledb": TimescaleDBAdapter,
        "csv": CSVAdapter,
    }
    if backend not in adapters:
        raise ValueError(f"unknown backend: {backend!r}, expected one of {list(adapters)}")
    return adapters[backend](**config)
```

- [ ] **Step 6: Run tests**

Run: `uv run --directory $GEN pytest tests/test_adapters.py -v`
Expected: All PASS.

- [ ] **Step 7: Commit**

```bash
git add $GEN/src/slo_generator/adapters/
git add $GEN/tests/test_adapters.py
git commit -m "feat: add BaseAdapter + CSVAdapter"
```

---

## Task 9: PrometheusAdapter

**Files:**
- Create: `generator/src/slo_generator/adapters/prometheus.py`
- Modify: `generator/tests/test_adapters.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_adapters.py`:

```python
class TestPrometheusAdapter:
    def _make_shaped_df(self) -> pd.DataFrame:
        """Minimal Prometheus-shaped DataFrame for testing."""
        return pd.DataFrame({
            "timestamp": pd.to_datetime(["2026-03-20T12:00:00Z", "2026-03-20T12:00:30Z"], utc=True),
            "metric": ["http_requests_total", "http_requests_total"],
            "value": [100.0, 200.0],
            "service": ["frontend", "frontend"],
            "host": ["host1", "host1"],
            "instance": ["frontend-host1:8080", "frontend-host1:8080"],
            "job": ["app", "app"],
            "le": [pd.NA, pd.NA],
            "status_code": ["200", "200"],
        })

    def test_writes_openmetrics_format(self, tmp_path: Path):
        from slo_generator.adapters.prometheus import PrometheusAdapter

        output = tmp_path / "test.om"
        df = self._make_shaped_df()

        with PrometheusAdapter(output) as adapter:
            adapter.write_chunk(df)

        content = output.read_text()
        assert "# TYPE http_requests_total counter" in content
        assert "# EOF" in content

    def test_groups_histogram_by_label_and_timestamp(self, tmp_path: Path):
        from slo_generator.adapters.prometheus import PrometheusAdapter

        ts = pd.to_datetime("2026-03-20T12:00:00Z", utc=True)
        df = pd.DataFrame({
            "timestamp": [ts, ts, ts, ts],
            "metric": [
                "http_request_duration_seconds_bucket",
                "http_request_duration_seconds_bucket",
                "http_request_duration_seconds_sum",
                "http_request_duration_seconds_count",
            ],
            "value": [50.0, 100.0, 5.0, 100.0],
            "service": ["frontend"] * 4,
            "host": ["host1"] * 4,
            "instance": ["frontend-host1:8080"] * 4,
            "job": ["app"] * 4,
            "le": ["0.1", "+Inf", pd.NA, pd.NA],
            "status_code": [pd.NA] * 4,
        })

        output = tmp_path / "hist.om"
        with PrometheusAdapter(output) as adapter:
            adapter.write_chunk(df)

        lines = output.read_text().splitlines()
        # bucket, sum, count should appear together (not scattered)
        bucket_indices = [i for i, l in enumerate(lines) if "bucket" in l]
        sum_indices = [i for i, l in enumerate(lines) if "_sum" in l and not l.startswith("#")]
        count_indices = [i for i, l in enumerate(lines) if "_count" in l and not l.startswith("#")]

        if bucket_indices and sum_indices and count_indices:
            # sum and count should come right after last bucket
            assert sum_indices[0] > bucket_indices[-1]
            assert count_indices[0] > sum_indices[0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory $GEN pytest tests/test_adapters.py::TestPrometheusAdapter -v`
Expected: ImportError.

- [ ] **Step 3: Implement `adapters/prometheus.py`**

Key requirements:
- Write `# HELP` and `# TYPE` headers per metric family
- Group histogram bucket/sum/count by `(label_set, timestamp)`
- Write `# EOF` on close
- Include `run_promtool()` static method for TSDB backfill

- [ ] **Step 4: Run tests**

Run: `uv run --directory $GEN pytest tests/test_adapters.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add $GEN/src/slo_generator/adapters/prometheus.py generator/tests/test_adapters.py
git commit -m "feat: add PrometheusAdapter with correct OpenMetrics grouping"
```

---

## Task 10: InfluxDBAdapter

**Files:**
- Create: `generator/src/slo_generator/adapters/influxdb.py`
- Modify: `generator/tests/test_adapters.py`

- [ ] **Step 1: Write failing test for line protocol generation**

Add to `tests/test_adapters.py`:

```python
class TestInfluxDBAdapter:
    def test_generates_line_protocol(self):
        from slo_generator.adapters.influxdb import InfluxDBAdapter

        df = pd.DataFrame({
            "timestamp": pd.to_datetime(["2026-03-20T12:00:00Z"], utc=True),
            "measurement": ["http_requests_total"],
            "service": ["frontend"],
            "host": ["host1"],
            "value": [100.0],
            "rate": [3.33],
            "le": [pd.NA],
            "status_code": ["200"],
        })

        lines = InfluxDBAdapter._to_line_protocol(df)
        assert len(lines) == 1
        assert lines[0].startswith("http_requests_total,")
        assert "service=frontend" in lines[0]
        assert "value=100.0" in lines[0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory $GEN pytest tests/test_adapters.py::TestInfluxDBAdapter -v`
Expected: ImportError.

- [ ] **Step 3: Implement `adapters/influxdb.py`**

Key requirements:
- `_to_line_protocol()` as a static/class method for testability (no connection needed)
- `write_chunk()` calls `_to_line_protocol()` then batch-writes via `influxdb_client`
- `ensure_dbrp_mapping()` on first write
- Connection params from constructor args or env vars

- [ ] **Step 4: Run tests**

Run: `uv run --directory $GEN pytest tests/test_adapters.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add $GEN/src/slo_generator/adapters/influxdb.py generator/tests/test_adapters.py
git commit -m "feat: add InfluxDBAdapter with line protocol + DBRP mapping"
```

---

## Task 11: TimescaleDBAdapter

**Files:**
- Create: `generator/src/slo_generator/adapters/timescaledb.py`
- Modify: `generator/tests/test_adapters.py`

- [ ] **Step 1: Write failing test for DDL generation**

Add to `tests/test_adapters.py`:

```python
class TestTimescaleDBAdapter:
    def test_generates_create_table_ddl(self):
        from slo_generator.adapters.timescaledb import TimescaleDBAdapter

        ddl = TimescaleDBAdapter.create_table_ddl()
        assert "CREATE TABLE" in ddl
        assert "timestamp" in ddl
        assert "metric" in ddl
        assert "hypertable" in ddl.lower() or "create_hypertable" in ddl.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory $GEN pytest tests/test_adapters.py::TestTimescaleDBAdapter -v`
Expected: ImportError.

- [ ] **Step 3: Implement `adapters/timescaledb.py`**

Key requirements:
- `create_table_ddl()` returns the CREATE TABLE + `create_hypertable` SQL
- `write_chunk()` uses psycopg `COPY` protocol for bulk insert
- Connection DSN from constructor or env var
- Creates table on first write if not exists

- [ ] **Step 4: Run tests**

Run: `uv run --directory $GEN pytest tests/test_adapters.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add $GEN/src/slo_generator/adapters/timescaledb.py generator/tests/test_adapters.py
git commit -m "feat: add TimescaleDBAdapter with COPY protocol + hypertable DDL"
```

---

## Task 12: Pipeline + CLI

**Files:**
- Create: `generator/src/slo_generator/pipeline.py`
- Create: `generator/src/slo_generator/cli.py`
- Create: `generator/tests/test_pipeline.py`
- Delete: `generator/main.py`
- Delete: `generator/scenarios/` (old)
- Delete: `generator/adapters/` (old)

- [ ] **Step 1: Write failing tests for pipeline**

```python
"""Tests for the pipeline wiring."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest


class TestPipeline:
    def test_csv_roundtrip(self, tmp_path: Path):
        """Scenario → RawShaper → CSVAdapter → readable CSV."""
        from slo_generator.pipeline import run_pipeline
        from slo_generator.scenarios.healthy import HealthyScenario

        start = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        end = start + timedelta(minutes=5)
        scenario = HealthyScenario(start, end)

        output = tmp_path / "test.csv"
        run_pipeline(
            scenario=scenario,
            backends=["csv"],
            output_dir=tmp_path,
            scenario_name="healthy",
        )

        csv_path = tmp_path / "healthy.csv"
        assert csv_path.exists()
        df = pd.read_csv(csv_path)
        assert len(df) > 0

    def test_prometheus_pipeline_produces_om_file(self, tmp_path: Path):
        """Scenario → PrometheusShaper → PrometheusAdapter → .om file."""
        from slo_generator.pipeline import run_pipeline
        from slo_generator.scenarios.healthy import HealthyScenario

        start = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        end = start + timedelta(minutes=5)
        scenario = HealthyScenario(start, end)

        run_pipeline(
            scenario=scenario,
            backends=["prometheus"],
            output_dir=tmp_path,
            scenario_name="healthy",
            prometheus_scrape_interval=30,
        )

        om_path = tmp_path / "healthy_metrics.om"
        assert om_path.exists()
        content = om_path.read_text()
        assert "# EOF" in content
        assert "http_requests_total" in content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory $GEN pytest tests/test_pipeline.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `pipeline.py`**

```python
"""Pipeline wiring: scenario → shaper → adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.console import Console

from slo_generator.adapters import get_adapter
from slo_generator.shapers import get_shaper

console = Console()


def run_pipeline(
    scenario: Any,
    backends: list[str],
    output_dir: Path,
    scenario_name: str,
    resolution_seconds: int = 1,
    prometheus_scrape_interval: int = 30,
    influxdb_url: str | None = None,
    influxdb_token: str | None = None,
    influxdb_org: str | None = None,
    influxdb_bucket: str | None = None,
    timescaledb_dsn: str | None = None,
    run_promtool: bool = False,
    prometheus_data_dir: Path | None = None,
) -> dict[str, bool]:
    """Run the generation pipeline for one scenario across all requested backends.

    Returns a dict of backend → success (True/False).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, bool] = {}

    # Build (shaper, adapter) pairs
    pairs = []
    for backend in backends:
        try:
            shaper_kwargs: dict[str, Any] = {}
            adapter_kwargs: dict[str, Any] = {}

            if backend == "prometheus":
                shaper_kwargs["scrape_interval"] = prometheus_scrape_interval
                adapter_kwargs["output_path"] = output_dir / f"{scenario_name}_metrics.om"
            elif backend == "influxdb":
                adapter_kwargs.update(
                    url=influxdb_url, token=influxdb_token,
                    org=influxdb_org, bucket=influxdb_bucket,
                )
            elif backend == "timescaledb":
                adapter_kwargs["dsn"] = timescaledb_dsn
            elif backend == "csv":
                adapter_kwargs["output_path"] = output_dir / f"{scenario_name}.csv"

            shaper = get_shaper(backend, **shaper_kwargs)
            adapter = get_adapter(backend, **adapter_kwargs)
            pairs.append((backend, shaper, adapter))
        except Exception as exc:
            console.print(f"[yellow]Skipping {backend}: {exc}[/yellow]")
            results[backend] = False

    # Stream chunks through all pipelines
    for chunk in scenario.generate(resolution_seconds=resolution_seconds):
        for backend, shaper, adapter in pairs:
            try:
                for shaped in shaper.shape(chunk):
                    adapter.write_chunk(shaped)
            except Exception as exc:
                console.print(f"[red]{backend} write failed: {exc}[/red]")
                results[backend] = False

    # Finalize
    for backend, shaper, adapter in pairs:
        try:
            for shaped in shaper.finalize():
                adapter.write_chunk(shaped)
            adapter.close()
            if backend not in results:
                results[backend] = True
            console.print(f"[green]{backend}: done[/green]")
        except Exception as exc:
            console.print(f"[red]{backend} finalize failed: {exc}[/red]")
            results[backend] = False

    # Optional promtool backfill
    if run_promtool and results.get("prometheus") and prometheus_data_dir:
        from slo_generator.adapters.prometheus import PrometheusAdapter
        om_path = output_dir / f"{scenario_name}_metrics.om"
        PrometheusAdapter.run_promtool(om_path, prometheus_data_dir)

    return results
```

- [ ] **Step 4: Implement `cli.py`**

Click CLI with the options from the spec. Calls `run_pipeline()` for each scenario.

- [ ] **Step 5: Delete old files**

```bash
rm $GEN/main.py
rm -rf $GEN/scenarios/ $GEN/adapters/
```

(The old `scenarios/` and `adapters/` directories at top level, not the ones under `src/`.)

- [ ] **Step 6: Run tests**

Run: `uv run --directory $GEN pytest tests/ -v`
Expected: All PASS.

- [ ] **Step 7: Commit**

```bash
git add $GEN/src/slo_generator/pipeline.py generator/src/slo_generator/cli.py
git add $GEN/tests/test_pipeline.py
git rm $GEN/main.py
git rm -r generator/scenarios/ generator/adapters/
git commit -m "feat: add pipeline wiring + CLI, delete old code"
```

---

## Task 13: Dockerfile + Docker Compose

**Files:**
- Modify: `generator/Dockerfile`
- Modify: `docker-compose.yml`
- Modify: `grafana/provisioning/datasources/all.yml`

- [ ] **Step 1: Rewrite Dockerfile**

```dockerfile
FROM python:3.13-slim

# Install promtool for TSDB backfill
ARG PROMETHEUS_VERSION=2.51.0
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -sSL "https://github.com/prometheus/prometheus/releases/download/v${PROMETHEUS_VERSION}/prometheus-${PROMETHEUS_VERSION}.linux-amd64.tar.gz" \
       | tar -xz --strip-components=1 -C /usr/local/bin \
           "prometheus-${PROMETHEUS_VERSION}.linux-amd64/promtool" \
    && apt-get remove -y curl && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src/ src/
RUN uv sync --frozen --all-extras --no-dev

ENTRYPOINT ["uv", "run", "slo-generate"]
```

- [ ] **Step 2: Update `docker-compose.yml`**

Add `timescaledb-metrics` service. Update generator `command`, `depends_on`, and `volumes`.

- [ ] **Step 3: Add TimescaleDB datasource to Grafana provisioning**

Add the PostgreSQL datasource block to `grafana/provisioning/datasources/all.yml`.

- [ ] **Step 4: Test Docker build**

Run: `docker compose -f $BASE/docker-compose.yml build generator`
Expected: Build succeeds.

- [ ] **Step 5: Commit**

```bash
git add $GEN/Dockerfile $BASE/docker-compose.yml $BASE/grafana/provisioning/datasources/all.yml
git commit -m "infra: update Dockerfile for uv, add TimescaleDB to docker-compose"
```

---

## Task 14: End-to-End Docker Test

- [ ] **Step 1: Run `make up`**

Run: `make -C $BASE up`
Expected: All services start, generator exits 0.

- [ ] **Step 2: Verify Prometheus has data**

Run: `curl -s 'http://localhost:9090/api/v1/query?query=http_requests_total'`
Expected: JSON response with metric data (status: "success").

- [ ] **Step 3: Verify InfluxDB has data**

Run: `curl -s 'http://localhost:8086/query?db=slo-metrics&q=SELECT+count(value)+FROM+http_requests_total' -u admin:slo-test-token`
Expected: JSON response with count > 0.

- [ ] **Step 4: Verify TimescaleDB has data**

Run: `docker exec slo_timescaledb psql -U metrics -d slo_metrics -c "SELECT count(*) FROM metrics;"`
Expected: Count > 0.

- [ ] **Step 5: Verify Grafana dashboards load**

Open http://localhost:3000 in browser, check all three dashboards show data.

- [ ] **Step 6: Commit any fixes**

```bash
git add -u $BASE/
git commit -m "fix: end-to-end docker integration fixes"
```

---

## Task 15: Multi-Datasource Dashboards

**Files:**
- Modify: `grafana/dashboard_config.yaml`
- Modify: `grafana/generate_dashboard.py`
- Modify: `grafana/templates/dashboard.json.j2`

- [ ] **Step 1: Extend `dashboard_config.yaml`**

Change `query` field to `queries` dict with `prometheus`, `influxql`, `sql` keys for each panel. Keep `prometheus` as the primary (maps to existing `query` values). Write appropriate InfluxQL and SQL equivalents for all 18 panels.

- [ ] **Step 2: Update `generate_dashboard.py`**

Modify `render_dashboard()` to render three dashboard JSON files from the same config, one per datasource. The datasource name and query key are passed to the Jinja2 template.

- [ ] **Step 3: Update `dashboard.json.j2`**

Parameterize the `datasource` field and query source. The template should accept a `datasource_name` and `query_key` variable.

- [ ] **Step 4: Regenerate and validate**

Run: `uv run --directory $BASE/grafana python generate_dashboard.py`
(Requires jinja2 and pyyaml — these are in `$BASE/grafana/requirements.txt`, install via `uv pip install -r $BASE/grafana/requirements.txt` first if needed.)
Expected: Three JSON files created in `$BASE/grafana/dashboards/`.

- [ ] **Step 5: Update Grafana provisioning**

Update `grafana/provisioning/dashboards/all.yml` if needed (it already watches the folder).

- [ ] **Step 6: Commit**

```bash
git add $BASE/grafana/
git commit -m "feat: generate dashboards for Prometheus, InfluxDB, and TimescaleDB"
```

---

## Task 16: Update Documentation

**Files:**
- Modify: `CLAUDE.md`
- Modify: `Makefile`
- Modify: `README.md`

- [ ] **Step 1: Update `CLAUDE.md`**

Update file map, commands, design decisions to reflect new architecture.

- [ ] **Step 2: Update `Makefile`**

Update `make up`, `make gen-csv`, etc. to use `uv run slo-generate` instead of `python main.py`.

- [ ] **Step 3: Update `README.md`**

Reflect new CLI, new backends, CSV input capability.

- [ ] **Step 4: Commit**

```bash
git add $BASE/CLAUDE.md $BASE/Makefile $BASE/README.md
git commit -m "docs: update documentation for refactored generator"
```
