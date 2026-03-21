# Timeline Composer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add YAML-based timeline composition to the SLO test data generator — compose continuous multi-day timelines from a healthy baseline plus event splices (outage, memory leak, traffic spike, step change, polska easter egg).

**Architecture:** A `TimelineComposer` sits above existing scenarios, yielding composed profile DataFrame chunks. It generates healthy baseline, then for each event, splices event data over the baseline using `generate_window()` on `BaseScenario`. Shapers and adapters are unchanged — they receive the same profile chunks as before.

**Tech Stack:** Python 3.13, pandas, numpy, click, pyyaml, uv package manager.

**Spec:** `docs/superpowers/specs/2026-03-21-timeline-composer-design.md`

**Base paths:**
- `$BASE` = `observability_stack/integration-test`
- `$GEN` = `$BASE/generator`
- `$SRC` = `$GEN/src/slo_generator`
- `$TESTS` = `$GEN/tests`

**Run tests with:** `uv run --directory $GEN pytest tests/ -v`

**Important context:**
- This is a standalone Python package inside the tropek repo, NOT part of the main tropek API
- Uses `uv` as package manager — always `uv run --directory $GEN` for Python execution
- No `cd && command` chaining — use `uv run --directory` and `git -C` per CLAUDE.md
- All imports at the top of files (project rule)
- The generator lives in a worktree at `.worktrees/generator-refactor` on branch `feat/generator-refactor`

---

## File Map

### New Files

| File | Purpose |
|---|---|
| `$SRC/composer.py` | `TimelineComposer`, `TimelineConfig`, `EventSpec`, YAML parsing, duration string parser |
| `$SRC/scenarios/memory_leak.py` | `MemoryLeakScenario` — exponential latency growth over days/weeks |
| `$SRC/scenarios/traffic_spike.py` | `TrafficSpikeScenario` — sudden burst causing 429 or 5xx |
| `$SRC/scenarios/step_change.py` | `StepChangeScenario` — sustained level shift |
| `$SRC/scenarios/polska.py` | `PolskaScenario` — easter egg using Poland contour |
| `$SRC/scenarios/polska_contour.py` | Poland border coordinate data (~200 normalized points) |
| `$TESTS/test_composer.py` | Timeline composition tests |
| `$BASE/timelines/quick-test.yaml` | 7-day timeline with one outage (Docker default) |
| `$BASE/timelines/evaluation-30d.yaml` | 30-day quality gate testing timeline |
| `$BASE/timelines/change-detection-60d.yaml` | 60-day change point detection timeline |
| `$BASE/timelines/easter-egg.yaml` | Polska scenario timeline |

### Modified Files

| File | Change |
|---|---|
| `$GEN/pyproject.toml` | Add `pyyaml>=6.0` dependency |
| `$SRC/scenarios/base.py` | Add `event_mode` to `__init__`, add `generate_window()` method |
| `$SRC/scenarios/outage.py` | Support `event_mode=True` |
| `$SRC/scenarios/degradation.py` | Support `event_mode=True` |
| `$SRC/scenarios/__init__.py` | Register new scenarios in factory |
| `$SRC/cli.py` | Add `--timeline` flag, metadata JSON output |
| `$BASE/grafana/generate_dashboard.py` | Read metadata JSON for time range |
| `$BASE/grafana/dashboard_config.yaml` | Remove hardcoded time range (set by generator) |
| `$BASE/docker-compose.yml` | Updated generator command for timeline mode |
| `$BASE/justfile` | New timeline-related recipes |
| `$BASE/CLAUDE.md` | Document timeline commands |

### Unchanged Files

Shapers (`$SRC/shapers/*`), adapters (`$SRC/adapters/*`), pipeline (`$SRC/pipeline.py`),
constants (`$SRC/constants.py`), `$SRC/scenarios/healthy.py`, `$SRC/scenarios/csv_input.py`.

---

## Task 1: Add PyYAML dependency

**Files:**
- Modify: `$GEN/pyproject.toml`

- [ ] **Step 1: Add pyyaml to dependencies**

In `$GEN/pyproject.toml`, add `"pyyaml>=6.0"` to the `dependencies` list:

```toml
dependencies = [
    "pandas>=2.2",
    "numpy>=1.26",
    "click>=8.1",
    "rich>=13.7",
    "pyyaml>=6.0",
]
```

- [ ] **Step 2: Run uv sync**

Run: `uv sync --directory $GEN`
Expected: resolves and installs pyyaml

- [ ] **Step 3: Verify import works**

Run: `uv run --directory $GEN python -c "import yaml; print(yaml.__version__)"`
Expected: prints version number (e.g. `6.0.2`)

- [ ] **Step 4: Commit**

```
git -C .worktrees/generator-refactor add $GEN/pyproject.toml $GEN/uv.lock
git -C .worktrees/generator-refactor commit -m "feat: add pyyaml dependency for timeline YAML parsing"
```

---

## Task 2: Add `event_mode` and `generate_window` to BaseScenario

**Files:**
- Modify: `$SRC/scenarios/base.py`
- Test: `$TESTS/test_scenarios.py`

- [ ] **Step 1: Write tests for generate_window**

Add to `$TESTS/test_scenarios.py`:

```python
class TestBaseScenarioGenerateWindow:
    def test_generate_window_returns_dataframe_with_correct_schema(self):
        from slo_generator.scenarios.healthy import HealthyScenario

        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=24)
        scenario = HealthyScenario(start, end)

        # Request a 10-minute sub-window at 30s resolution
        window_start = start + timedelta(hours=5)
        window_end = window_start + timedelta(minutes=10)
        df = scenario.generate_window(window_start, window_end, resolution_seconds=30)

        validate_profile_schema(df)
        # 10 minutes at 30s = 20 timestamps × 6 service-host combos = 120 rows
        assert len(df) == 20 * 6

    def test_generate_window_timestamps_within_bounds(self):
        from slo_generator.scenarios.healthy import HealthyScenario

        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=24)
        scenario = HealthyScenario(start, end)

        window_start = start + timedelta(hours=3)
        window_end = window_start + timedelta(minutes=5)
        df = scenario.generate_window(window_start, window_end, resolution_seconds=1)

        assert df["timestamp"].min() >= pd.Timestamp(window_start, tz="UTC")
        assert df["timestamp"].max() < pd.Timestamp(window_end, tz="UTC")

    def test_generate_window_empty_when_zero_duration(self):
        from slo_generator.scenarios.healthy import HealthyScenario

        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=1)
        scenario = HealthyScenario(start, end)

        df = scenario.generate_window(start, start, resolution_seconds=1)
        assert len(df) == 0

    def test_event_mode_defaults_to_false(self):
        from slo_generator.scenarios.healthy import HealthyScenario

        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=1)
        scenario = HealthyScenario(start, end)
        assert scenario.event_mode is False

    def test_event_mode_can_be_set(self):
        from slo_generator.scenarios.healthy import HealthyScenario

        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=1)
        scenario = HealthyScenario(start, end, event_mode=True)
        assert scenario.event_mode is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory $GEN pytest tests/test_scenarios.py::TestBaseScenarioGenerateWindow -v`
Expected: FAIL — `generate_window` not defined, `event_mode` not accepted

- [ ] **Step 3: Implement changes to BaseScenario**

Modify `$SRC/scenarios/base.py`:

```python
class BaseScenario(ABC):
    """Abstract base for all data generation scenarios."""

    name: str = "base"

    def __init__(self, start: datetime, end: datetime, *, event_mode: bool = False):
        self.start = start
        self.end = end
        self.event_mode = event_mode
        self._rng = np.random.default_rng(seed=42)

    def generate_window(
        self,
        window_start: datetime,
        window_end: datetime,
        resolution_seconds: int = 1,
    ) -> pd.DataFrame:
        """Generate a single profile DataFrame for an arbitrary sub-window.

        Unlike generate() which yields hour-sized chunks over the full range,
        this returns one DataFrame covering exactly [window_start, window_end)
        at the given resolution. Used by the composer for event splicing.
        """
        timestamps = pd.date_range(
            window_start,
            window_end,
            freq=f"{resolution_seconds}s",
            inclusive="left",
            tz="UTC",
        ).as_unit("ns")
        if len(timestamps) == 0:
            return pd.DataFrame(columns=PROFILE_COLUMNS)
        return self._build_chunk(timestamps)

    # ... existing generate(), _build_chunk(), _build_profiles() unchanged ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory $GEN pytest tests/test_scenarios.py -v`
Expected: ALL PASS (existing tests + new tests)

- [ ] **Step 5: Commit**

```
git -C .worktrees/generator-refactor add $SRC/scenarios/base.py $TESTS/test_scenarios.py
git -C .worktrees/generator-refactor commit -m "feat: add event_mode and generate_window to BaseScenario"
```

---

## Task 3: Add event_mode to OutageScenario

**Files:**
- Modify: `$SRC/scenarios/outage.py`
- Test: `$TESTS/test_scenarios.py`

- [ ] **Step 1: Write test for outage event_mode**

Add to `$TESTS/test_scenarios.py`:

```python
class TestOutageEventMode:
    def test_event_mode_outage_fills_entire_window(self):
        """In event_mode, outage starts at the beginning, not at 60%."""
        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(minutes=45)  # 30min outage + 10min recovery + 5min margin
        scenario = OutageScenario(start, end, event_mode=True, recovery_minutes=10)

        chunks = list(scenario.generate(resolution_seconds=30))
        df = pd.concat(chunks)
        api = df[(df["service"] == "api") & (df["host"] == "host1")]

        # Error rate should be high near the start (no pre-outage healthy phase)
        early = api[api["timestamp"] < start + timedelta(minutes=10)]
        assert early["error_rate"].mean() > 0.3

    def test_event_mode_recovery_ends_at_window_end(self):
        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(minutes=40)
        scenario = OutageScenario(start, end, event_mode=True, recovery_minutes=10)

        # Recovery end should be at end of window
        assert scenario.recovery_end == end

    def test_standalone_mode_unchanged(self):
        """Default (event_mode=False) should still work as before."""
        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=12)
        scenario = OutageScenario(start, end)

        # Outage should start at 60% mark
        expected_start = start + timedelta(seconds=12 * 3600 * 0.60)
        assert abs((scenario.outage_start - expected_start).total_seconds()) < 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory $GEN pytest tests/test_scenarios.py::TestOutageEventMode -v`
Expected: FAIL — `event_mode` not accepted by OutageScenario

- [ ] **Step 3: Implement event_mode in OutageScenario**

Modify `$SRC/scenarios/outage.py` — update `__init__` to accept and use `event_mode`:

```python
class OutageScenario(BaseScenario):
    """Simulates a full outage: high errors, low throughput, high latency."""

    name = "outage"

    def __init__(
        self,
        start: datetime,
        end: datetime,
        *,
        event_mode: bool = False,
        outage_duration_minutes: int = 30,
        recovery_minutes: int = 10,
    ):
        super().__init__(start, end, event_mode=event_mode)
        if event_mode:
            self.outage_start = start
            self.outage_end = end - timedelta(minutes=recovery_minutes)
            self.recovery_end = end
        else:
            total = (end - start).total_seconds()
            self.outage_start = start + timedelta(seconds=total * 0.60)
            self.outage_end = self.outage_start + timedelta(minutes=outage_duration_minutes)
            self.recovery_end = self.outage_end + timedelta(minutes=recovery_minutes)
```

Note: `_build_profiles` is unchanged — it already uses `self.outage_start`, `self.outage_end`,
`self.recovery_end` for phase masks. Setting those differently in `__init__` is sufficient.

- [ ] **Step 4: Run all tests**

Run: `uv run --directory $GEN pytest tests/test_scenarios.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```
git -C .worktrees/generator-refactor add $SRC/scenarios/outage.py $TESTS/test_scenarios.py
git -C .worktrees/generator-refactor commit -m "feat: add event_mode to OutageScenario"
```

---

## Task 4: Add event_mode to DegradationScenario

**Files:**
- Modify: `$SRC/scenarios/degradation.py`
- Test: `$TESTS/test_scenarios.py`

- [ ] **Step 1: Write test for degradation event_mode**

Add to `$TESTS/test_scenarios.py`:

```python
class TestDegradationEventMode:
    def test_event_mode_ramp_starts_at_window_start(self):
        """In event_mode, degradation starts immediately, not at 65%."""
        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=2)
        scenario = DegradationScenario(start, end, event_mode=True, ramp_minutes=5)

        chunks = list(scenario.generate(resolution_seconds=30))
        df = pd.concat(chunks)
        api = df[(df["service"] == "api") & (df["host"] == "host1")]

        # After the 5-minute ramp, latency should be at degraded level
        post_ramp = api[api["timestamp"] >= start + timedelta(minutes=10)]
        assert post_ramp["p99_latency"].mean() > 0.3  # 5x of 0.08 = 0.4

    def test_event_mode_no_healthy_pre_phase(self):
        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=1)
        scenario = DegradationScenario(start, end, event_mode=True, ramp_minutes=5)

        # deploy_start should be at start of window
        assert scenario.deploy_start == start

    def test_standalone_mode_unchanged(self):
        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=12)
        scenario = DegradationScenario(start, end)

        expected_start = start + timedelta(seconds=12 * 3600 * 0.65)
        assert abs((scenario.deploy_start - expected_start).total_seconds()) < 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory $GEN pytest tests/test_scenarios.py::TestDegradationEventMode -v`
Expected: FAIL

- [ ] **Step 3: Implement event_mode in DegradationScenario**

Modify `$SRC/scenarios/degradation.py` — update `__init__`:

```python
class DegradationScenario(BaseScenario):
    """Simulates a bad deployment: latency 5x, error rate 5x, throughput unchanged."""

    name = "degradation"

    def __init__(
        self,
        start: datetime,
        end: datetime,
        *,
        event_mode: bool = False,
        ramp_minutes: int = 5,
        latency_multiplier: float = 5.0,
        error_rate_multiplier: float = 5.0,
    ):
        super().__init__(start, end, event_mode=event_mode)
        if event_mode:
            self.deploy_start = start
        else:
            total = (end - start).total_seconds()
            self.deploy_start = start + timedelta(seconds=total * 0.65)
        self.ramp_end = self.deploy_start + timedelta(minutes=ramp_minutes)
        self.lat_mult = latency_multiplier
        self.err_mult = error_rate_multiplier
```

- [ ] **Step 4: Run all tests**

Run: `uv run --directory $GEN pytest tests/test_scenarios.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```
git -C .worktrees/generator-refactor add $SRC/scenarios/degradation.py $TESTS/test_scenarios.py
git -C .worktrees/generator-refactor commit -m "feat: add event_mode to DegradationScenario"
```

---

## Task 5: MemoryLeakScenario

**Files:**
- Create: `$SRC/scenarios/memory_leak.py`
- Test: `$TESTS/test_scenarios.py`

- [ ] **Step 1: Write tests**

Add to `$TESTS/test_scenarios.py`:

```python
class TestMemoryLeakScenario:
    def test_latency_increases_exponentially(self):
        from slo_generator.scenarios.memory_leak import MemoryLeakScenario

        start = datetime(2026, 3, 1, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=48)
        scenario = MemoryLeakScenario(start, end, growth_rate=0.01)

        chunks = list(scenario.generate(resolution_seconds=60))
        df = pd.concat(chunks)
        api = df[(df["service"] == "api") & (df["host"] == "host1")]

        early = api[api["timestamp"] < start + timedelta(hours=6)]
        late = api[
            (api["timestamp"] >= start + timedelta(hours=40))
            & (api["timestamp"] < start + timedelta(hours=47))  # before crash
        ]

        # Late latency should be significantly higher than early
        assert late["p99_latency"].mean() > early["p99_latency"].mean() * 2

    def test_memory_grows_over_time(self):
        from slo_generator.scenarios.memory_leak import MemoryLeakScenario

        start = datetime(2026, 3, 1, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=48)
        scenario = MemoryLeakScenario(start, end, growth_rate=0.01)

        chunks = list(scenario.generate(resolution_seconds=60))
        df = pd.concat(chunks)
        api = df[(df["service"] == "api") & (df["host"] == "host1")]

        early = api[api["timestamp"] < start + timedelta(hours=6)]
        late = api[api["timestamp"] >= start + timedelta(hours=40)]

        assert late["memory_bytes"].mean() > early["memory_bytes"].mean()

    def test_crash_at_end_spikes_errors(self):
        from slo_generator.scenarios.memory_leak import MemoryLeakScenario

        start = datetime(2026, 3, 1, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=24)
        scenario = MemoryLeakScenario(start, end, crash_at_end=True)

        chunks = list(scenario.generate(resolution_seconds=60))
        df = pd.concat(chunks)
        api = df[(df["service"] == "api") & (df["host"] == "host1")]

        # Last hour should have very high error rates
        final_hour = api[api["timestamp"] >= end - timedelta(hours=1)]
        assert final_hour["error_rate"].mean() > 0.5

    def test_profile_schema_valid(self):
        from slo_generator.scenarios.memory_leak import MemoryLeakScenario

        start = datetime(2026, 3, 1, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=2)
        scenario = MemoryLeakScenario(start, end)

        chunks = list(scenario.generate(resolution_seconds=30))
        df = pd.concat(chunks)
        validate_profile_schema(df)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory $GEN pytest tests/test_scenarios.py::TestMemoryLeakScenario -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement MemoryLeakScenario**

Create `$SRC/scenarios/memory_leak.py`:

```python
"""Memory leak scenario — exponential latency growth over days/weeks until crash."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from slo_generator.constants import HEALTHY_DEFAULTS, HOST_FACTORS, SERVICE_FACTORS
from slo_generator.scenarios.base import BaseScenario


class MemoryLeakScenario(BaseScenario):
    """Simulates a slow memory leak causing exponential latency degradation."""

    name = "memory_leak"

    def __init__(
        self,
        start: datetime,
        end: datetime,
        *,
        event_mode: bool = True,
        growth_rate: float = 0.003,
        crash_at_end: bool = True,
    ):
        super().__init__(start, end, event_mode=event_mode)
        self.growth_rate = growth_rate
        self.crash_at_end = crash_at_end

    def _build_profiles(
        self,
        timestamps: pd.DatetimeIndex,
        service: str,
        host: str,
    ) -> pd.DataFrame:
        n = len(timestamps)
        sf = SERVICE_FACTORS.get(service, 1.0)
        hf = HOST_FACTORS.get(host, 1.0)
        base = HEALTHY_DEFAULTS

        total_seconds = (self.end - self.start).total_seconds()
        ts_epoch = timestamps.astype(np.int64) / 1e9
        start_epoch = self.start.timestamp()

        # Normalized progress 0→1 over the event window
        progress = np.clip((ts_epoch - start_epoch) / total_seconds, 0.0, 1.0)

        # Exponential growth: tau scales so growth_rate * exp(1/tau) is the peak
        tau = 1.0 / np.log(1.0 / self.growth_rate + 1.0)
        growth = 1.0 + self.growth_rate * np.expm1(progress / tau)

        # Latency grows exponentially
        p50 = base["p50_latency"] * growth
        p99 = base["p99_latency"] * growth

        # Memory grows linearly toward 95% of a notional 2GB limit
        max_memory = 2 * 1024 * 1024 * 1024 * 0.95
        base_mem = base["memory_bytes"] * hf
        memory = base_mem + progress * (max_memory - base_mem)

        # Throughput decreases as GC pressure mounts
        throughput = np.maximum(
            10.0,
            base["throughput_rps"] * sf * hf * (1.0 - 0.3 * progress),
        )

        # Error rate stays low until later phases
        error_rate = np.where(
            progress < 0.8,
            base["error_rate"],
            base["error_rate"] + (progress - 0.8) * 5 * 0.1,
        )

        # CPU increases with memory pressure
        cpu = np.clip(base["cpu_percent"] + progress * 30, 0.0, 100.0)

        # Crash phase: final hour
        if self.crash_at_end:
            crash_threshold = 1.0 - (3600 / total_seconds)  # last hour
            crash_mask = progress >= crash_threshold
            crash_progress = np.clip(
                (progress - crash_threshold) / (1.0 - crash_threshold), 0.0, 1.0
            )
            throughput = np.where(crash_mask, np.maximum(0.1, 10 * (1 - crash_progress)), throughput)
            error_rate = np.where(crash_mask, np.minimum(1.0, 0.5 + 0.5 * crash_progress), error_rate)
            p99 = np.where(crash_mask, 30.0, p99)  # timeout
            p50 = np.where(crash_mask, 10.0, p50)
            cpu = np.where(crash_mask, 99.0, cpu)

        return pd.DataFrame(
            {
                "timestamp": timestamps,
                "throughput_rps": throughput,
                "error_rate": error_rate,
                "p50_latency": p50,
                "p99_latency": p99,
                "cpu_percent": cpu,
                "memory_bytes": memory,
            }
        )
```

- [ ] **Step 4: Run tests**

Run: `uv run --directory $GEN pytest tests/test_scenarios.py::TestMemoryLeakScenario -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```
git -C .worktrees/generator-refactor add $SRC/scenarios/memory_leak.py $TESTS/test_scenarios.py
git -C .worktrees/generator-refactor commit -m "feat: add MemoryLeakScenario"
```

---

## Task 6: TrafficSpikeScenario

**Files:**
- Create: `$SRC/scenarios/traffic_spike.py`
- Test: `$TESTS/test_scenarios.py`

- [ ] **Step 1: Write tests**

Add to `$TESTS/test_scenarios.py`:

```python
class TestTrafficSpikeScenario:
    def test_throughput_spikes_in_rate_limit_mode(self):
        from slo_generator.scenarios.traffic_spike import TrafficSpikeScenario

        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=2)
        scenario = TrafficSpikeScenario(
            start, end, spike_multiplier=5.0, error_mode="rate_limit",
        )

        chunks = list(scenario.generate(resolution_seconds=30))
        df = pd.concat(chunks)
        api = df[(df["service"] == "api") & (df["host"] == "host1")]

        # Peak throughput should be much higher than baseline
        assert api["throughput_rps"].max() > 300  # 5x of ~100

    def test_overload_mode_increases_latency(self):
        from slo_generator.scenarios.traffic_spike import TrafficSpikeScenario

        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=2)
        scenario = TrafficSpikeScenario(
            start, end, spike_multiplier=5.0, error_mode="overload",
        )

        chunks = list(scenario.generate(resolution_seconds=30))
        df = pd.concat(chunks)
        api = df[(df["service"] == "api") & (df["host"] == "host1")]

        # In overload mode, latency should spike
        assert api["p99_latency"].max() > 1.0

    def test_rate_limit_mode_keeps_latency_low(self):
        from slo_generator.scenarios.traffic_spike import TrafficSpikeScenario

        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=2)
        scenario = TrafficSpikeScenario(
            start, end, spike_multiplier=5.0, error_mode="rate_limit",
        )

        chunks = list(scenario.generate(resolution_seconds=30))
        df = pd.concat(chunks)
        api = df[(df["service"] == "api") & (df["host"] == "host1")]

        # In rate_limit mode, latency stays reasonable
        assert api["p99_latency"].max() < 1.0

    def test_profile_schema_valid(self):
        from slo_generator.scenarios.traffic_spike import TrafficSpikeScenario

        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=1)
        scenario = TrafficSpikeScenario(start, end)

        chunks = list(scenario.generate(resolution_seconds=30))
        df = pd.concat(chunks)
        validate_profile_schema(df)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory $GEN pytest tests/test_scenarios.py::TestTrafficSpikeScenario -v`
Expected: FAIL

- [ ] **Step 3: Implement TrafficSpikeScenario**

Create `$SRC/scenarios/traffic_spike.py`:

```python
"""Traffic spike scenario — sudden burst causing 429 or 5xx errors."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from slo_generator.constants import HEALTHY_DEFAULTS, HOST_FACTORS, SERVICE_FACTORS
from slo_generator.scenarios.base import BaseScenario


class TrafficSpikeScenario(BaseScenario):
    """Simulates a sudden traffic burst with rate-limit or overload behavior."""

    name = "traffic_spike"

    def __init__(
        self,
        start: datetime,
        end: datetime,
        *,
        event_mode: bool = True,
        spike_multiplier: float = 5.0,
        error_mode: str = "rate_limit",
        ramp_minutes: int = 5,
        sustain_fraction: float = 0.6,
    ):
        super().__init__(start, end, event_mode=event_mode)
        self.spike_multiplier = spike_multiplier
        self.error_mode = error_mode
        self.ramp_minutes = ramp_minutes
        self.sustain_fraction = sustain_fraction

    def _build_profiles(
        self,
        timestamps: pd.DatetimeIndex,
        service: str,
        host: str,
    ) -> pd.DataFrame:
        n = len(timestamps)
        sf = SERVICE_FACTORS.get(service, 1.0)
        hf = HOST_FACTORS.get(host, 1.0)
        base = HEALTHY_DEFAULTS
        base_throughput = base["throughput_rps"] * sf * hf

        total_seconds = (self.end - self.start).total_seconds()
        ts_epoch = timestamps.astype(np.int64) / 1e9
        start_epoch = self.start.timestamp()
        progress = np.clip((ts_epoch - start_epoch) / total_seconds, 0.0, 1.0)

        ramp_frac = self.ramp_minutes * 60 / total_seconds
        sustain_end = ramp_frac + self.sustain_fraction
        taper_end = 1.0

        # Traffic envelope: ramp → sustain → taper
        envelope = np.where(
            progress < ramp_frac,
            1.0 + (self.spike_multiplier - 1.0) * (progress / ramp_frac),
            np.where(
                progress < sustain_end,
                self.spike_multiplier,
                np.where(
                    progress < taper_end,
                    self.spike_multiplier * (1.0 - (progress - sustain_end) / (taper_end - sustain_end)),
                    1.0,
                ),
            ),
        )

        incoming_traffic = base_throughput * envelope
        capacity = base_throughput * 2.0  # system handles ~2x baseline

        if self.error_mode == "rate_limit":
            throughput = incoming_traffic  # total requests (including 429s)
            excess = np.maximum(0.0, incoming_traffic - capacity)
            error_rate = np.clip(excess / np.maximum(incoming_traffic, 1.0), 0.0, 0.9)
            p50 = np.full(n, base["p50_latency"])
            p99 = np.full(n, base["p99_latency"]) * (1.0 + 0.2 * (envelope - 1.0))
            cpu = np.clip(base["cpu_percent"] * np.minimum(envelope, 2.0), 0.0, 95.0)
        else:  # overload
            # System saturates: throughput collapses above capacity
            served = np.where(
                incoming_traffic <= capacity,
                incoming_traffic,
                capacity * (capacity / incoming_traffic),
            )
            throughput = served
            excess = np.maximum(0.0, incoming_traffic - capacity)
            error_rate = np.clip(0.5 * excess / np.maximum(incoming_traffic, 1.0), 0.0, 0.95)
            # Latency spikes with queue depth
            queue_factor = np.maximum(1.0, envelope ** 2)
            p50 = base["p50_latency"] * queue_factor
            p99 = base["p99_latency"] * queue_factor * 2.0
            cpu = np.clip(base["cpu_percent"] * np.minimum(envelope, 2.5), 0.0, 100.0)

        return pd.DataFrame(
            {
                "timestamp": timestamps,
                "throughput_rps": throughput,
                "error_rate": error_rate,
                "p50_latency": p50,
                "p99_latency": p99,
                "cpu_percent": cpu,
                "memory_bytes": np.full(n, base["memory_bytes"] * hf),
            }
        )
```

- [ ] **Step 4: Run tests**

Run: `uv run --directory $GEN pytest tests/test_scenarios.py::TestTrafficSpikeScenario -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```
git -C .worktrees/generator-refactor add $SRC/scenarios/traffic_spike.py $TESTS/test_scenarios.py
git -C .worktrees/generator-refactor commit -m "feat: add TrafficSpikeScenario with rate_limit and overload modes"
```

---

## Task 7: StepChangeScenario

**Files:**
- Create: `$SRC/scenarios/step_change.py`
- Test: `$TESTS/test_scenarios.py`

- [ ] **Step 1: Write tests**

Add to `$TESTS/test_scenarios.py`:

```python
class TestStepChangeScenario:
    def test_latency_shifts_to_new_level(self):
        from slo_generator.scenarios.step_change import StepChangeScenario

        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=4)
        scenario = StepChangeScenario(start, end, latency_multiplier=2.0, ramp_minutes=5)

        chunks = list(scenario.generate(resolution_seconds=30))
        df = pd.concat(chunks)
        api = df[(df["service"] == "api") & (df["host"] == "host1")]

        # After ramp, latency should be near 2x
        post_ramp = api[api["timestamp"] >= start + timedelta(minutes=10)]
        assert post_ramp["p99_latency"].mean() > 0.12  # ~2x of 0.08

    def test_throughput_shifts_to_new_level(self):
        from slo_generator.scenarios.step_change import StepChangeScenario

        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=4)
        scenario = StepChangeScenario(start, end, throughput_multiplier=0.7, ramp_minutes=2)

        chunks = list(scenario.generate(resolution_seconds=30))
        df = pd.concat(chunks)
        api = df[(df["service"] == "api") & (df["host"] == "host1")]

        post_ramp = api[api["timestamp"] >= start + timedelta(minutes=5)]
        # Throughput should be ~70% of baseline (~100)
        assert post_ramp["throughput_rps"].mean() < 80

    def test_profile_schema_valid(self):
        from slo_generator.scenarios.step_change import StepChangeScenario

        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=1)
        scenario = StepChangeScenario(start, end)

        chunks = list(scenario.generate(resolution_seconds=30))
        df = pd.concat(chunks)
        validate_profile_schema(df)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory $GEN pytest tests/test_scenarios.py::TestStepChangeScenario -v`
Expected: FAIL

- [ ] **Step 3: Implement StepChangeScenario**

Create `$SRC/scenarios/step_change.py`:

```python
"""Step change scenario — sustained level shift after config change or capacity reduction."""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from slo_generator.constants import HEALTHY_DEFAULTS, HOST_FACTORS, SERVICE_FACTORS
from slo_generator.scenarios.base import BaseScenario


class StepChangeScenario(BaseScenario):
    """Simulates a sustained level shift with brief ramp to new baseline."""

    name = "step_change"

    def __init__(
        self,
        start: datetime,
        end: datetime,
        *,
        event_mode: bool = True,
        latency_multiplier: float = 1.5,
        throughput_multiplier: float = 1.0,
        error_rate_multiplier: float = 1.0,
        ramp_minutes: int = 2,
    ):
        super().__init__(start, end, event_mode=event_mode)
        self.lat_mult = latency_multiplier
        self.tput_mult = throughput_multiplier
        self.err_mult = error_rate_multiplier
        self.ramp_end = start + timedelta(minutes=ramp_minutes)

    def _build_profiles(
        self,
        timestamps: pd.DatetimeIndex,
        service: str,
        host: str,
    ) -> pd.DataFrame:
        n = len(timestamps)
        sf = SERVICE_FACTORS.get(service, 1.0)
        hf = HOST_FACTORS.get(host, 1.0)
        base = HEALTHY_DEFAULTS

        ts_epoch = timestamps.astype(np.int64) / 1e9
        start_epoch = self.start.timestamp()
        ramp_end_epoch = self.ramp_end.timestamp()
        ramp_duration = (self.ramp_end - self.start).total_seconds()

        ramp_frac = np.clip(
            (ts_epoch - start_epoch) / max(ramp_duration, 1.0), 0.0, 1.0
        )

        is_ramping = ts_epoch < ramp_end_epoch

        def interpolate(base_val: float, multiplier: float) -> np.ndarray:
            target = base_val * multiplier
            return np.where(is_ramping, base_val + ramp_frac * (target - base_val), target)

        throughput = np.maximum(10.0, interpolate(base["throughput_rps"] * sf * hf, self.tput_mult))
        error_rate = np.clip(interpolate(base["error_rate"], self.err_mult), 0.0, 1.0)
        p50 = interpolate(base["p50_latency"], self.lat_mult)
        p99 = interpolate(base["p99_latency"], self.lat_mult)
        cpu = np.clip(interpolate(base["cpu_percent"], self.lat_mult * 0.8), 0.0, 100.0)

        return pd.DataFrame(
            {
                "timestamp": timestamps,
                "throughput_rps": throughput,
                "error_rate": error_rate,
                "p50_latency": p50,
                "p99_latency": p99,
                "cpu_percent": cpu,
                "memory_bytes": np.full(n, base["memory_bytes"] * hf),
            }
        )
```

- [ ] **Step 4: Run tests**

Run: `uv run --directory $GEN pytest tests/test_scenarios.py::TestStepChangeScenario -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```
git -C .worktrees/generator-refactor add $SRC/scenarios/step_change.py $TESTS/test_scenarios.py
git -C .worktrees/generator-refactor commit -m "feat: add StepChangeScenario"
```

---

## Task 8: PolskaScenario (Easter Egg)

**Files:**
- Create: `$SRC/scenarios/polska_contour.py`
- Create: `$SRC/scenarios/polska.py`
- Test: `$TESTS/test_scenarios.py`

- [ ] **Step 1: Write tests**

Add to `$TESTS/test_scenarios.py`:

```python
class TestPolskaScenario:
    def test_profile_schema_valid(self):
        from slo_generator.scenarios.polska import PolskaScenario

        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=4)
        scenario = PolskaScenario(start, end)

        chunks = list(scenario.generate(resolution_seconds=30))
        df = pd.concat(chunks)
        validate_profile_schema(df)

    def test_throughput_varies_with_contour(self):
        from slo_generator.scenarios.polska import PolskaScenario

        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=4)
        scenario = PolskaScenario(start, end)

        chunks = list(scenario.generate(resolution_seconds=30))
        df = pd.concat(chunks)
        api = df[(df["service"] == "api") & (df["host"] == "host1")]

        # Throughput should vary (not a flat line) following the contour
        assert api["throughput_rps"].std() > 5.0

    def test_latency_anticorrelated_with_throughput(self):
        from slo_generator.scenarios.polska import PolskaScenario

        start = datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=4)
        scenario = PolskaScenario(start, end)

        chunks = list(scenario.generate(resolution_seconds=60))
        df = pd.concat(chunks)
        api = df[(df["service"] == "api") & (df["host"] == "host1")]

        # Throughput and latency should be roughly anti-correlated
        corr = api["throughput_rps"].corr(api["p99_latency"])
        assert corr < 0  # negative correlation
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory $GEN pytest tests/test_scenarios.py::TestPolskaScenario -v`
Expected: FAIL

- [ ] **Step 3: Create polska_contour.py**

Create `$SRC/scenarios/polska_contour.py` with a simplified Poland border as normalized
coordinates. This is a data-only file — approximately 100 (x, y) pairs tracing Poland's
border clockwise from the northwest corner, normalized to x∈[0,1], y∈[0,1].

The agent implementing this task should:
1. Create a simplified Poland border outline with ~100 coordinate pairs
2. Normalize x (west→east mapped to 0→1) and y (south→north mapped to 0→1)
3. Store as two lists: `POLSKA_UPPER` (northern border, maps to throughput) and
   `POLSKA_LOWER` (southern border, maps to latency)
4. Both lists should have the same x-coordinates so they can be interpolated

```python
"""Poland border contour coordinates — data only, no logic."""

# Normalized (x, y) coordinates for Poland's border.
# x: 0=west, 1=east. y: 0=south, 1=north.
# Split into upper (northern) and lower (southern) contours.

# x coordinates shared by both contours (west to east, ~100 points)
POLSKA_X: list[float] = [
    # ... ~100 evenly spaced values from 0.0 to 1.0
]

# Northern contour y-values (used for throughput envelope)
POLSKA_UPPER: list[float] = [
    # ... y values tracing the northern border
]

# Southern contour y-values (used for latency envelope, inverted)
POLSKA_LOWER: list[float] = [
    # ... y values tracing the southern border
]
```

The agent should generate realistic-looking coordinate data that approximates
Poland's shape. Exact geographic accuracy is not required — it's an easter egg.
The key is that UPPER and LOWER create a recognizable Poland-like outline when
plotted as two curves.

- [ ] **Step 4: Create polska.py**

Create `$SRC/scenarios/polska.py`:

```python
"""Polska scenario — easter egg using Poland's geographic contour as metric envelope."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from slo_generator.constants import HEALTHY_DEFAULTS, HOST_FACTORS, SERVICE_FACTORS
from slo_generator.scenarios.base import BaseScenario
from slo_generator.scenarios.polska_contour import POLSKA_LOWER, POLSKA_UPPER, POLSKA_X


class PolskaScenario(BaseScenario):
    """Generates metrics shaped like Poland's geographic contour."""

    name = "polska"

    def __init__(
        self,
        start: datetime,
        end: datetime,
        *,
        event_mode: bool = True,
        noise_amplitude: float = 0.05,
        throughput_range: tuple[float, float] = (50.0, 200.0),
        latency_range: tuple[float, float] = (0.01, 0.5),
    ):
        super().__init__(start, end, event_mode=event_mode)
        self.noise_amplitude = noise_amplitude
        self.throughput_range = throughput_range
        self.latency_range = latency_range

    def _build_profiles(
        self,
        timestamps: pd.DatetimeIndex,
        service: str,
        host: str,
    ) -> pd.DataFrame:
        n = len(timestamps)
        sf = SERVICE_FACTORS.get(service, 1.0)
        hf = HOST_FACTORS.get(host, 1.0)
        base = HEALTHY_DEFAULTS

        total_seconds = (self.end - self.start).total_seconds()
        ts_epoch = timestamps.astype(np.int64) / 1e9
        start_epoch = self.start.timestamp()
        progress = np.clip((ts_epoch - start_epoch) / total_seconds, 0.0, 1.0)

        # Interpolate contour values at each timestamp's progress
        upper = np.interp(progress, POLSKA_X, POLSKA_UPPER)
        lower = np.interp(progress, POLSKA_X, POLSKA_LOWER)

        # Add noise
        noise_t = self._rng.normal(0, self.noise_amplitude, n)
        noise_l = self._rng.normal(0, self.noise_amplitude, n)

        # Map upper contour → throughput
        tmin, tmax = self.throughput_range
        throughput = np.clip(
            tmin + (upper + noise_t) * (tmax - tmin) * sf * hf,
            10.0,
            tmax * 2,
        )

        # Map lower contour → latency (inverted: lower contour = higher latency)
        lmin, lmax = self.latency_range
        p99 = np.clip(
            lmin + (1.0 - lower + noise_l) * (lmax - lmin),
            lmin,
            lmax * 2,
        )
        p50 = p99 * 0.3

        # Derived metrics
        error_rate = np.full(n, base["error_rate"])
        cpu = np.clip(30 + upper * 40, 0.0, 100.0)
        memory = np.full(n, base["memory_bytes"] * hf)

        return pd.DataFrame(
            {
                "timestamp": timestamps,
                "throughput_rps": throughput,
                "error_rate": error_rate,
                "p50_latency": p50,
                "p99_latency": p99,
                "cpu_percent": cpu,
                "memory_bytes": memory,
            }
        )
```

- [ ] **Step 5: Run tests**

Run: `uv run --directory $GEN pytest tests/test_scenarios.py::TestPolskaScenario -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```
git -C .worktrees/generator-refactor add $SRC/scenarios/polska.py $SRC/scenarios/polska_contour.py $TESTS/test_scenarios.py
git -C .worktrees/generator-refactor commit -m "feat: add PolskaScenario easter egg"
```

---

## Task 9: Update scenario factory

**Files:**
- Modify: `$SRC/scenarios/__init__.py`

- [ ] **Step 1: Register new scenarios**

Update `$SRC/scenarios/__init__.py`:

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
    from slo_generator.scenarios.memory_leak import MemoryLeakScenario
    from slo_generator.scenarios.outage import OutageScenario
    from slo_generator.scenarios.polska import PolskaScenario
    from slo_generator.scenarios.step_change import StepChangeScenario
    from slo_generator.scenarios.traffic_spike import TrafficSpikeScenario

    scenarios = {
        "healthy": HealthyScenario,
        "outage": OutageScenario,
        "degradation": DegradationScenario,
        "csv": CSVScenario,
        "memory_leak": MemoryLeakScenario,
        "traffic_spike": TrafficSpikeScenario,
        "step_change": StepChangeScenario,
        "polska": PolskaScenario,
    }
    if name not in scenarios:
        raise ValueError(f"unknown scenario: {name!r}, expected one of {list(scenarios)}")
    return scenarios[name](**kwargs)
```

- [ ] **Step 2: Verify all existing tests still pass**

Run: `uv run --directory $GEN pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```
git -C .worktrees/generator-refactor add $SRC/scenarios/__init__.py
git -C .worktrees/generator-refactor commit -m "feat: register new scenarios in factory"
```

---

## Task 10: TimelineComposer — config and YAML parsing

**Files:**
- Create: `$SRC/composer.py`
- Test: `$TESTS/test_composer.py`

- [ ] **Step 1: Write tests for YAML parsing and config**

Create `$TESTS/test_composer.py`:

```python
"""Tests for timeline composition."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tests.conftest import validate_profile_schema


class TestDurationParsing:
    def test_parse_seconds(self):
        from slo_generator.composer import parse_duration

        assert parse_duration("30s") == timedelta(seconds=30)

    def test_parse_minutes(self):
        from slo_generator.composer import parse_duration

        assert parse_duration("5m") == timedelta(minutes=5)

    def test_parse_hours(self):
        from slo_generator.composer import parse_duration

        assert parse_duration("720h") == timedelta(hours=720)

    def test_parse_days(self):
        from slo_generator.composer import parse_duration

        assert parse_duration("30d") == timedelta(days=30)

    def test_invalid_duration_raises(self):
        from slo_generator.composer import parse_duration

        with pytest.raises(ValueError, match="invalid duration"):
            parse_duration("abc")


class TestTimelineConfig:
    def test_from_yaml_minimal(self, tmp_path: Path):
        from slo_generator.composer import TimelineComposer

        yaml_content = """
timeline:
  start: "2026-03-01T00:00:00Z"
  duration: 168h
  events: []
"""
        yaml_path = tmp_path / "test.yaml"
        yaml_path.write_text(yaml_content)

        composer = TimelineComposer.from_yaml(yaml_path)
        assert composer.config.start == datetime(2026, 3, 1, tzinfo=UTC)
        assert composer.config.end == datetime(2026, 3, 8, tzinfo=UTC)
        assert composer.config.resolution_seconds == 30  # default
        assert composer.config.baseline == "healthy"  # default
        assert len(composer.config.events) == 0

    def test_from_yaml_with_end_instead_of_duration(self, tmp_path: Path):
        from slo_generator.composer import TimelineComposer

        yaml_content = """
timeline:
  start: "2026-03-01T00:00:00Z"
  end: "2026-03-08T00:00:00Z"
  events: []
"""
        yaml_path = tmp_path / "test.yaml"
        yaml_path.write_text(yaml_content)

        composer = TimelineComposer.from_yaml(yaml_path)
        assert composer.config.end == datetime(2026, 3, 8, tzinfo=UTC)

    def test_from_yaml_with_events(self, tmp_path: Path):
        from slo_generator.composer import TimelineComposer

        yaml_content = """
timeline:
  start: "2026-03-01T00:00:00Z"
  duration: 168h
  resolution: 10s
  events:
    - type: outage
      at: 100h
      duration: 30m
      restart_gap: 1m
      resolution: 1s
      params:
        recovery_minutes: 5
"""
        yaml_path = tmp_path / "test.yaml"
        yaml_path.write_text(yaml_content)

        composer = TimelineComposer.from_yaml(yaml_path)
        assert composer.config.resolution_seconds == 10
        assert len(composer.config.events) == 1

        event = composer.config.events[0]
        assert event.type == "outage"
        assert event.at == timedelta(hours=100)
        assert event.duration == timedelta(minutes=30)
        assert event.restart_gap == timedelta(minutes=1)
        assert event.resolution == 1
        assert event.params == {"recovery_minutes": 5}

    def test_validates_overlapping_events(self, tmp_path: Path):
        from slo_generator.composer import TimelineComposer

        yaml_content = """
timeline:
  start: "2026-03-01T00:00:00Z"
  duration: 168h
  events:
    - type: outage
      at: 100h
      duration: 5h
    - type: degradation
      at: 103h
      duration: 5h
"""
        yaml_path = tmp_path / "test.yaml"
        yaml_path.write_text(yaml_content)

        with pytest.raises(ValueError, match="overlap"):
            TimelineComposer.from_yaml(yaml_path)

    def test_validates_event_exceeds_timeline(self, tmp_path: Path):
        from slo_generator.composer import TimelineComposer

        yaml_content = """
timeline:
  start: "2026-03-01T00:00:00Z"
  duration: 24h
  events:
    - type: outage
      at: 23h
      duration: 3h
"""
        yaml_path = tmp_path / "test.yaml"
        yaml_path.write_text(yaml_content)

        with pytest.raises(ValueError, match="exceeds"):
            TimelineComposer.from_yaml(yaml_path)

    def test_validates_event_resolution_coarser_than_global(self, tmp_path: Path):
        from slo_generator.composer import TimelineComposer

        yaml_content = """
timeline:
  start: "2026-03-01T00:00:00Z"
  duration: 24h
  resolution: 30s
  events:
    - type: outage
      at: 12h
      duration: 1h
      resolution: 60s
"""
        yaml_path = tmp_path / "test.yaml"
        yaml_path.write_text(yaml_content)

        with pytest.raises(ValueError, match="coarser"):
            TimelineComposer.from_yaml(yaml_path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory $GEN pytest tests/test_composer.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement composer.py (config + parsing only)**

Create `$SRC/composer.py`:

```python
"""Timeline composer — composes continuous timelines from baseline + event splices."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from slo_generator.constants import PROFILE_COLUMNS
from slo_generator.scenarios import get_scenario


def parse_duration(s: str) -> timedelta:
    """Parse a duration string like '30s', '5m', '2h', '30d' into a timedelta."""
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([smhd])", s.strip())
    if not match:
        raise ValueError(f"invalid duration string: {s!r}, expected format like '30s', '5m', '2h', '30d'")
    value = float(match.group(1))
    unit = match.group(2)
    units = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}
    return timedelta(**{units[unit]: value})


def _parse_resolution_seconds(s: str) -> int:
    """Parse a duration string and return total seconds as int."""
    td = parse_duration(s)
    return int(td.total_seconds())


def _parse_datetime(s: str) -> datetime:
    """Parse an ISO 8601 datetime string to a timezone-aware datetime."""
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


@dataclass
class EventSpec:
    """Specification for a single event in a timeline."""

    type: str
    at: timedelta
    duration: timedelta
    restart_gap: timedelta = field(default_factory=timedelta)
    resolution: int | None = None
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class TimelineConfig:
    """Parsed and validated timeline configuration."""

    start: datetime
    end: datetime
    resolution_seconds: int
    baseline: str
    events: list[EventSpec]


class TimelineComposer:
    """Composes a continuous timeline from a healthy baseline + event splices."""

    def __init__(self, config: TimelineConfig):
        self.config = config

    @classmethod
    def from_yaml(cls, path: Path) -> TimelineComposer:
        """Load and validate a timeline from a YAML file."""
        with open(path) as f:
            raw = yaml.safe_load(f)

        tl = raw["timeline"]
        start = _parse_datetime(tl["start"])

        if "duration" in tl:
            end = start + parse_duration(tl["duration"])
        elif "end" in tl:
            end = _parse_datetime(tl["end"])
        else:
            raise ValueError("timeline must have either 'duration' or 'end'")

        resolution_seconds = _parse_resolution_seconds(tl.get("resolution", "30s"))
        baseline = tl.get("baseline", "healthy")

        events = []
        for raw_event in tl.get("events", []):
            event = EventSpec(
                type=raw_event["type"],
                at=parse_duration(str(raw_event["at"])),
                duration=parse_duration(str(raw_event["duration"])),
                restart_gap=parse_duration(str(raw_event.get("restart_gap", "0s"))),
                resolution=(
                    _parse_resolution_seconds(str(raw_event["resolution"]))
                    if "resolution" in raw_event
                    else None
                ),
                params=raw_event.get("params", {}),
            )
            events.append(event)

        config = TimelineConfig(
            start=start,
            end=end,
            resolution_seconds=resolution_seconds,
            baseline=baseline,
            events=events,
        )

        _validate_config(config)
        return cls(config)

    def generate(
        self,
        resolution_seconds: int = 30,
        chunk_hours: int = 1,
    ) -> Iterator[pd.DataFrame]:
        """Yield composed profile DataFrame chunks."""
        raise NotImplementedError("composition logic in next task")

    def write_metadata(self, output_dir: Path) -> None:
        """Write metadata JSON for dashboard time range configuration."""
        raise NotImplementedError("metadata output in CLI task")


def _validate_config(config: TimelineConfig) -> None:
    """Validate timeline configuration rules."""
    total_duration = config.end - config.start

    # Sort events by start time for overlap check
    sorted_events = sorted(config.events, key=lambda e: e.at)

    for event in sorted_events:
        if event.at + event.duration > total_duration:
            raise ValueError(
                f"event {event.type!r} at {event.at} + duration {event.duration} "
                f"exceeds timeline duration {total_duration}"
            )

    # Check resolution direction (event resolution must be finer than global)
    for event in sorted_events:
        if event.resolution is not None and event.resolution > config.resolution_seconds:
            raise ValueError(
                f"event {event.type!r} resolution ({event.resolution}s) is coarser "
                f"than global resolution ({config.resolution_seconds}s)"
            )

    # Check for overlaps
    for i in range(len(sorted_events) - 1):
        current = sorted_events[i]
        next_event = sorted_events[i + 1]
        current_end = current.at + current.duration + current.restart_gap
        if current_end > next_event.at:
            raise ValueError(
                f"events overlap: {current.type!r} ends at {current_end} "
                f"but {next_event.type!r} starts at {next_event.at}"
            )
```

- [ ] **Step 4: Run tests**

Run: `uv run --directory $GEN pytest tests/test_composer.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```
git -C .worktrees/generator-refactor add $SRC/composer.py $TESTS/test_composer.py
git -C .worktrees/generator-refactor commit -m "feat: add TimelineComposer config and YAML parsing"
```

---

## Task 11: TimelineComposer — composition algorithm

**Files:**
- Modify: `$SRC/composer.py`
- Test: `$TESTS/test_composer.py`

- [ ] **Step 1: Write tests for composition**

Add to `$TESTS/test_composer.py`:

```python
import pandas as pd


class TestTimelineComposition:
    def test_pure_baseline_generates_healthy_data(self, tmp_path: Path):
        from slo_generator.composer import TimelineComposer

        yaml_content = """
timeline:
  start: "2026-03-20T00:00:00Z"
  duration: 2h
  resolution: 30s
  events: []
"""
        yaml_path = tmp_path / "test.yaml"
        yaml_path.write_text(yaml_content)

        composer = TimelineComposer.from_yaml(yaml_path)
        chunks = list(composer.generate())

        assert len(chunks) == 2  # 2 hours = 2 chunks
        df = pd.concat(chunks)
        validate_profile_schema(df)
        assert (df["error_rate"] < 0.01).all()  # healthy

    def test_event_replaces_baseline_window(self, tmp_path: Path):
        from slo_generator.composer import TimelineComposer

        yaml_content = """
timeline:
  start: "2026-03-20T00:00:00Z"
  duration: 4h
  resolution: 30s
  events:
    - type: outage
      at: 1h
      duration: 30m
"""
        yaml_path = tmp_path / "test.yaml"
        yaml_path.write_text(yaml_content)

        composer = TimelineComposer.from_yaml(yaml_path)
        chunks = list(composer.generate())
        df = pd.concat(chunks)

        validate_profile_schema(df)

        api = df[(df["service"] == "api") & (df["host"] == "host1")]
        start = datetime(2026, 3, 20, tzinfo=UTC)

        # During outage window, error rate should be elevated
        outage_window = api[
            (api["timestamp"] >= start + timedelta(hours=1, minutes=5))
            & (api["timestamp"] < start + timedelta(hours=1, minutes=20))
        ]
        assert outage_window["error_rate"].mean() > 0.3

        # Before outage, should be healthy
        before = api[api["timestamp"] < start + timedelta(hours=1)]
        assert before["error_rate"].mean() < 0.01

    def test_restart_gap_creates_missing_data(self, tmp_path: Path):
        from slo_generator.composer import TimelineComposer

        yaml_content = """
timeline:
  start: "2026-03-20T00:00:00Z"
  duration: 2h
  resolution: 30s
  events:
    - type: outage
      at: 30m
      duration: 20m
      restart_gap: 5m
"""
        yaml_path = tmp_path / "test.yaml"
        yaml_path.write_text(yaml_content)

        composer = TimelineComposer.from_yaml(yaml_path)
        chunks = list(composer.generate())
        df = pd.concat(chunks)

        api = df[(df["service"] == "api") & (df["host"] == "host1")]
        start = datetime(2026, 3, 20, tzinfo=UTC)

        # There should be no data in the gap window (50min to 55min)
        gap_data = api[
            (api["timestamp"] >= start + timedelta(minutes=50))
            & (api["timestamp"] < start + timedelta(minutes=55))
        ]
        assert len(gap_data) == 0

    def test_event_resolution_override(self, tmp_path: Path):
        from slo_generator.composer import TimelineComposer

        yaml_content = """
timeline:
  start: "2026-03-20T00:00:00Z"
  duration: 2h
  resolution: 30s
  events:
    - type: step_change
      at: 30m
      duration: 30m
      resolution: 5s
"""
        yaml_path = tmp_path / "test.yaml"
        yaml_path.write_text(yaml_content)

        composer = TimelineComposer.from_yaml(yaml_path)
        chunks = list(composer.generate())
        df = pd.concat(chunks)

        api = df[(df["service"] == "api") & (df["host"] == "host1")]
        start = datetime(2026, 3, 20, tzinfo=UTC)

        # Event window should have finer resolution (5s = more data points)
        event_data = api[
            (api["timestamp"] >= start + timedelta(minutes=30))
            & (api["timestamp"] < start + timedelta(hours=1))
        ]
        baseline_data = api[api["timestamp"] < start + timedelta(minutes=30)]

        # More data points per minute in event window
        event_per_min = len(event_data) / 30
        baseline_per_min = len(baseline_data) / 30
        assert event_per_min > baseline_per_min * 3  # 5s vs 30s = 6x
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory $GEN pytest tests/test_composer.py::TestTimelineComposition -v`
Expected: FAIL — NotImplementedError

- [ ] **Step 3: Implement generate() method**

Replace the `generate` method stub in `$SRC/composer.py`:

```python
    def generate(
        self,
        resolution_seconds: int = 30,
        chunk_hours: int = 1,
    ) -> Iterator[pd.DataFrame]:
        """Yield composed profile DataFrame chunks.

        Uses self.config.resolution_seconds as the global resolution.
        The resolution_seconds parameter is kept for interface compatibility.
        """
        baseline = get_scenario(
            self.config.baseline, start=self.config.start, end=self.config.end
        )

        event_scenarios = []
        for event in sorted(self.config.events, key=lambda e: e.at):
            event_start = self.config.start + event.at
            event_end = event_start + event.duration
            scenario = get_scenario(
                event.type,
                start=event_start,
                end=event_end,
                event_mode=True,
                **event.params,
            )
            event_scenarios.append((event, scenario, event_start, event_end))

        chunk_start = self.config.start
        chunk_delta = timedelta(hours=chunk_hours)

        while chunk_start < self.config.end:
            chunk_end = min(chunk_start + chunk_delta, self.config.end)

            overlapping = [
                (ev, sc, es, ee)
                for ev, sc, es, ee in event_scenarios
                if es < chunk_end and ee > chunk_start
            ]

            if not overlapping:
                chunk = baseline.generate_window(
                    chunk_start, chunk_end, self.config.resolution_seconds
                )
            else:
                chunk = baseline.generate_window(
                    chunk_start, chunk_end, self.config.resolution_seconds
                )
                chunk = self._splice_events(
                    chunk, chunk_start, chunk_end, overlapping
                )

            if len(chunk) > 0:
                yield chunk

            chunk_start = chunk_end

    def _splice_events(
        self,
        chunk: pd.DataFrame,
        chunk_start: datetime,
        chunk_end: datetime,
        overlapping: list[tuple],
    ) -> pd.DataFrame:
        """Replace baseline rows with event data and apply restart gaps."""
        for event, scenario, ev_start, ev_end in overlapping:
            overlap_start = max(chunk_start, ev_start)
            overlap_end = min(chunk_end, ev_end)
            ev_resolution = event.resolution or self.config.resolution_seconds

            event_data = scenario.generate_window(
                overlap_start, overlap_end, ev_resolution
            )

            chunk = chunk[
                (chunk["timestamp"] < pd.Timestamp(overlap_start, tz="UTC"))
                | (chunk["timestamp"] >= pd.Timestamp(overlap_end, tz="UTC"))
            ]
            chunk = pd.concat([chunk, event_data], ignore_index=True)

            if event.restart_gap.total_seconds() > 0:
                gap_end = overlap_end + event.restart_gap
                chunk = chunk[
                    (chunk["timestamp"] < pd.Timestamp(overlap_end, tz="UTC"))
                    | (chunk["timestamp"] >= pd.Timestamp(gap_end, tz="UTC"))
                ]

        return chunk.sort_values("timestamp").reset_index(drop=True)
```

- [ ] **Step 4: Run tests**

Run: `uv run --directory $GEN pytest tests/test_composer.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run all tests**

Run: `uv run --directory $GEN pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```
git -C .worktrees/generator-refactor add $SRC/composer.py $TESTS/test_composer.py
git -C .worktrees/generator-refactor commit -m "feat: implement TimelineComposer composition algorithm"
```

---

## Task 12: CLI — add `--timeline` flag and metadata output

**Files:**
- Modify: `$SRC/cli.py`

- [ ] **Step 1: Update CLI with --timeline flag**

Modify `$SRC/cli.py`:

```python
"""CLI entry point for the SLO test data generator."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import click
from rich.console import Console

from slo_generator.pipeline import run_pipeline
from slo_generator.scenarios import get_scenario

console = Console()

SCENARIO_NAMES = ["healthy", "outage", "degradation"]
BACKEND_NAMES = ["prometheus", "influxdb", "timescaledb", "csv"]


@click.command()
@click.option(
    "--timeline",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Timeline YAML file for composed generation",
)
@click.option(
    "--scenarios", "-s", multiple=True, default=SCENARIO_NAMES, help="Scenarios to generate"
)
@click.option("--backends", "-b", multiple=True, default=["prometheus"], help="Output backends")
@click.option("--hours", type=int, default=24, help="Duration in hours")
@click.option("--resolution", type=int, default=1, help="Resolution in seconds")
@click.option(
    "--output-dir", type=click.Path(path_type=Path), default=Path("output"), help="Output directory"
)
@click.option("--scrape-interval", type=int, default=30, help="Prometheus scrape interval")
@click.option("--influxdb-url", envvar="INFLUXDB_URL", default=None)
@click.option("--influxdb-token", envvar="INFLUXDB_TOKEN", default=None)
@click.option("--influxdb-org", envvar="INFLUXDB_ORG", default=None)
@click.option("--influxdb-bucket", envvar="INFLUXDB_BUCKET", default=None)
@click.option("--timescaledb-dsn", envvar="TIMESCALEDB_DSN", default=None)
@click.option("--run-promtool/--no-promtool", default=False, help="Run promtool TSDB backfill")
@click.option("--prometheus-data-dir", type=click.Path(path_type=Path), default=None)
def main(
    timeline: Path | None,
    scenarios: tuple[str, ...],
    backends: tuple[str, ...],
    hours: int,
    resolution: int,
    output_dir: Path,
    scrape_interval: int,
    influxdb_url: str | None,
    influxdb_token: str | None,
    influxdb_org: str | None,
    influxdb_bucket: str | None,
    timescaledb_dsn: str | None,
    run_promtool: bool,
    prometheus_data_dir: Path | None,
) -> None:
    """Generate SLO test data for quality gate evaluation."""
    if timeline:
        _run_timeline_mode(
            timeline, backends, output_dir, scrape_interval,
            influxdb_url, influxdb_token, influxdb_org, influxdb_bucket,
            timescaledb_dsn, run_promtool, prometheus_data_dir,
        )
    else:
        _run_scenario_mode(
            scenarios, backends, hours, resolution, output_dir, scrape_interval,
            influxdb_url, influxdb_token, influxdb_org, influxdb_bucket,
            timescaledb_dsn, run_promtool, prometheus_data_dir,
        )


def _run_timeline_mode(
    timeline_path: Path,
    backends: tuple[str, ...],
    output_dir: Path,
    scrape_interval: int,
    influxdb_url: str | None,
    influxdb_token: str | None,
    influxdb_org: str | None,
    influxdb_bucket: str | None,
    timescaledb_dsn: str | None,
    run_promtool: bool,
    prometheus_data_dir: Path | None,
) -> None:
    """Run timeline composition mode."""
    from slo_generator.composer import TimelineComposer

    composer = TimelineComposer.from_yaml(timeline_path)
    config = composer.config

    console.print(f"[bold]Timeline mode: {timeline_path.name}[/bold]")
    console.print(f"  Time range: {config.start.isoformat()} → {config.end.isoformat()}")
    console.print(f"  Resolution: {config.resolution_seconds}s")
    console.print(f"  Events: {len(config.events)}")

    scenario_name = "timeline"
    results = run_pipeline(
        scenario=composer,
        backends=list(backends),
        output_dir=output_dir / scenario_name,
        scenario_name=scenario_name,
        resolution_seconds=config.resolution_seconds,
        prometheus_scrape_interval=scrape_interval,
        influxdb_url=influxdb_url,
        influxdb_token=influxdb_token,
        influxdb_org=influxdb_org,
        influxdb_bucket=influxdb_bucket,
        timescaledb_dsn=timescaledb_dsn,
        run_promtool=run_promtool,
        prometheus_data_dir=prometheus_data_dir,
    )

    for backend, success in results.items():
        status = "[green]✓[/green]" if success else "[red]✗[/red]"
        console.print(f"  {status} {backend}")

    # Write metadata JSON for dashboard time range
    _write_metadata(output_dir / scenario_name, config)
    console.print("\n[bold green]Done![/bold green]")


def _run_scenario_mode(
    scenarios: tuple[str, ...],
    backends: tuple[str, ...],
    hours: int,
    resolution: int,
    output_dir: Path,
    scrape_interval: int,
    influxdb_url: str | None,
    influxdb_token: str | None,
    influxdb_org: str | None,
    influxdb_bucket: str | None,
    timescaledb_dsn: str | None,
    run_promtool: bool,
    prometheus_data_dir: Path | None,
) -> None:
    """Run legacy per-scenario mode."""
    end = datetime.now(tz=UTC)
    start = end - timedelta(hours=hours)

    console.print(f"[bold]Generating {len(scenarios)} scenarios x {len(backends)} backends[/bold]")
    console.print(f"  Time range: {start.isoformat()} → {end.isoformat()}")
    console.print(f"  Resolution: {resolution}s")

    for scenario_name in scenarios:
        console.print(f"\n[bold cyan]Scenario: {scenario_name}[/bold cyan]")
        scenario = get_scenario(scenario_name, start=start, end=end)

        results = run_pipeline(
            scenario=scenario,
            backends=list(backends),
            output_dir=output_dir / scenario_name,
            scenario_name=scenario_name,
            resolution_seconds=resolution,
            prometheus_scrape_interval=scrape_interval,
            influxdb_url=influxdb_url,
            influxdb_token=influxdb_token,
            influxdb_org=influxdb_org,
            influxdb_bucket=influxdb_bucket,
            timescaledb_dsn=timescaledb_dsn,
            run_promtool=run_promtool,
            prometheus_data_dir=prometheus_data_dir,
        )

        for backend, success in results.items():
            status = "[green]✓[/green]" if success else "[red]✗[/red]"
            console.print(f"  {status} {backend}")

    console.print("\n[bold green]Done![/bold green]")


def _write_metadata(output_dir: Path, config: "TimelineConfig") -> None:
    """Write metadata JSON with timeline info for dashboard generation."""
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        "start": config.start.isoformat(),
        "end": config.end.isoformat(),
        "resolution_seconds": config.resolution_seconds,
        "events": [
            {
                "type": ev.type,
                "start": (config.start + ev.at).isoformat(),
                "end": (config.start + ev.at + ev.duration).isoformat(),
            }
            for ev in config.events
        ],
        "generated_at": datetime.now(tz=UTC).isoformat(),
    }
    metadata_path = output_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2))
```

Note: add `from __future__ import annotations` at top, and add the TYPE_CHECKING
import for `TimelineConfig` if needed for the type annotation on `_write_metadata`.

- [ ] **Step 2: Run all tests**

Run: `uv run --directory $GEN pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```
git -C .worktrees/generator-refactor add $SRC/cli.py
git -C .worktrees/generator-refactor commit -m "feat: add --timeline flag and metadata output to CLI"
```

---

## Task 13: Timeline pipeline integration test

**Files:**
- Modify: `$TESTS/test_pipeline.py`

- [ ] **Step 1: Write integration test**

Add to `$TESTS/test_pipeline.py`:

```python
class TestTimelinePipeline:
    def test_timeline_csv_roundtrip(self, tmp_path: Path):
        """TimelineComposer → RawShaper → CSVAdapter → readable CSV."""
        from slo_generator.composer import TimelineComposer
        from slo_generator.pipeline import run_pipeline

        yaml_content = """
timeline:
  start: "2026-03-20T00:00:00Z"
  duration: 2h
  resolution: 30s
  events:
    - type: outage
      at: 1h
      duration: 20m
"""
        yaml_path = tmp_path / "timeline.yaml"
        yaml_path.write_text(yaml_content)

        composer = TimelineComposer.from_yaml(yaml_path)
        results = run_pipeline(
            scenario=composer,
            backends=["csv"],
            output_dir=tmp_path,
            scenario_name="timeline",
            resolution_seconds=composer.config.resolution_seconds,
        )

        assert results["csv"] is True
        csv_path = tmp_path / "timeline.csv"
        assert csv_path.exists()
        df = pd.read_csv(csv_path)
        assert len(df) > 0
        # Should have data from both healthy and outage periods
        assert df["error_rate"].max() > 0.1  # outage period

    def test_timeline_prometheus_pipeline(self, tmp_path: Path):
        """TimelineComposer → PrometheusShaper → PrometheusAdapter → .om file."""
        from slo_generator.composer import TimelineComposer
        from slo_generator.pipeline import run_pipeline

        yaml_content = """
timeline:
  start: "2026-03-20T00:00:00Z"
  duration: 2h
  resolution: 30s
  events:
    - type: step_change
      at: 30m
      duration: 30m
      params:
        latency_multiplier: 2.0
"""
        yaml_path = tmp_path / "timeline.yaml"
        yaml_path.write_text(yaml_content)

        composer = TimelineComposer.from_yaml(yaml_path)
        results = run_pipeline(
            scenario=composer,
            backends=["prometheus"],
            output_dir=tmp_path,
            scenario_name="timeline",
            resolution_seconds=composer.config.resolution_seconds,
            prometheus_scrape_interval=30,
        )

        assert results["prometheus"] is True
        om_path = tmp_path / "timeline_metrics.om"
        assert om_path.exists()
        content = om_path.read_text()
        assert "# EOF" in content
        assert "http_requests_total" in content
```

- [ ] **Step 2: Run tests**

Run: `uv run --directory $GEN pytest tests/test_pipeline.py -v`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```
git -C .worktrees/generator-refactor add $TESTS/test_pipeline.py
git -C .worktrees/generator-refactor commit -m "feat: add timeline pipeline integration tests"
```

---

## Task 14: Dashboard time range from metadata

**Files:**
- Modify: `$BASE/grafana/generate_dashboard.py`
- Modify: `$BASE/grafana/dashboard_config.yaml`

- [ ] **Step 1: Update generate_dashboard.py to accept metadata**

Add a `--metadata` CLI argument to `generate_dashboard.py` and use it to set
`time_from` / `time_to` in the dashboard config. If no metadata is provided,
fall back to current behavior (`now-1h` / `now`).

```python
#!/usr/bin/env python3
"""Generate Grafana dashboard JSON files from a config YAML for multiple datasources."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

# ... DATASOURCES dict unchanged ...

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "dashboard_config.yaml"
TEMPLATES_DIR = BASE_DIR / "templates"
OUTPUT_DIR = BASE_DIR / "dashboards"


def get_time_range(metadata_path: Path | None) -> tuple[str, str]:
    """Return Grafana time range showing last 7 days of generated data."""
    if metadata_path and metadata_path.exists():
        meta = json.loads(metadata_path.read_text())
        end = datetime.fromisoformat(meta["end"])
        start = end - timedelta(days=7)
        return start.isoformat() + "Z", end.isoformat() + "Z"
    return "now-1h", "now"


def load_config(path: Path, metadata_path: Path | None = None) -> dict:
    """Load and parse the dashboard YAML config file."""
    with open(path) as f:
        config = yaml.safe_load(f)

    time_from, time_to = get_time_range(metadata_path)
    config["time_from"] = time_from
    config["time_to"] = time_to
    return config


# ... render_dashboard, validate_json unchanged ...


def generate_all_dashboards(metadata_path: Path | None = None) -> None:
    """Render one dashboard JSON file per datasource and write to the output directory."""
    config = load_config(CONFIG_PATH, metadata_path)
    OUTPUT_DIR.mkdir(exist_ok=True)

    # ... rest unchanged ...


if __name__ == "__main__":
    metadata_path = None
    if len(sys.argv) >= 3 and sys.argv[1] == "--metadata":
        metadata_path = Path(sys.argv[2])

    print(f"Generating dashboards from {CONFIG_PATH.relative_to(BASE_DIR)}")
    print(f"Output directory: {OUTPUT_DIR.relative_to(BASE_DIR)}/")
    print()
    generate_all_dashboards(metadata_path)
    print()
    print("Done.")
```

- [ ] **Step 2: Remove hardcoded time_from/time_to from dashboard_config.yaml**

In `$BASE/grafana/dashboard_config.yaml`, remove `time_from` and `time_to` lines
(they're now set programmatically by `load_config`). Or keep them as defaults that
get overridden:

```yaml
time_from: "now-7d"
time_to: "now"
```

- [ ] **Step 3: Verify dashboard generation still works**

Run: `uv run --directory $BASE/grafana python generate_dashboard.py`
Expected: generates 3 dashboard JSONs without errors

- [ ] **Step 4: Commit**

```
git -C .worktrees/generator-refactor add $BASE/grafana/generate_dashboard.py $BASE/grafana/dashboard_config.yaml
git -C .worktrees/generator-refactor commit -m "feat: dashboard time range from metadata JSON"
```

---

## Task 15: Example timeline YAML files

**Files:**
- Create: `$BASE/timelines/quick-test.yaml`
- Create: `$BASE/timelines/evaluation-30d.yaml`
- Create: `$BASE/timelines/change-detection-60d.yaml`
- Create: `$BASE/timelines/easter-egg.yaml`

- [ ] **Step 1: Create timeline files**

Create `$BASE/timelines/quick-test.yaml`:
```yaml
timeline:
  start: "2026-03-14T00:00:00Z"
  duration: 168h
  resolution: 30s
  baseline: healthy

  events:
    - type: outage
      at: 160h
      duration: 30m
      resolution: 5s
```

Create `$BASE/timelines/evaluation-30d.yaml`:
```yaml
timeline:
  start: "2026-02-19T00:00:00Z"
  duration: 720h
  resolution: 30s
  baseline: healthy

  events:
    - type: degradation
      at: 504h
      duration: 4h
      params:
        latency_multiplier: 3.0
        error_rate_multiplier: 2.0

    - type: outage
      at: 690h
      duration: 45m
      resolution: 1s
      restart_gap: 30s
```

Create `$BASE/timelines/change-detection-60d.yaml`:
```yaml
timeline:
  start: "2026-01-20T00:00:00Z"
  duration: 1440h
  resolution: 30s
  baseline: healthy

  events:
    - type: step_change
      at: 480h
      duration: 240h
      params:
        latency_multiplier: 1.3
        throughput_multiplier: 0.85

    - type: memory_leak
      at: 960h
      duration: 336h
      params:
        growth_rate: 0.005
        crash_at_end: true

    - type: traffic_spike
      at: 1380h
      duration: 3h
      params:
        spike_multiplier: 6.0
        error_mode: overload
      resolution: 5s
```

Create `$BASE/timelines/easter-egg.yaml`:
```yaml
timeline:
  start: "2026-03-20T00:00:00Z"
  duration: 48h
  resolution: 30s
  baseline: healthy

  events:
    - type: polska
      at: 6h
      duration: 36h
```

- [ ] **Step 2: Validate all YAML files parse correctly**

Run: `uv run --directory $GEN python -c "from slo_generator.composer import TimelineComposer; TimelineComposer.from_yaml(Path('$BASE/timelines/quick-test.yaml')); print('OK')"` (repeat for each file)

Or write a quick validation script. The composer's `from_yaml` will raise on invalid config.

- [ ] **Step 3: Commit**

```
git -C .worktrees/generator-refactor add $BASE/timelines/
git -C .worktrees/generator-refactor commit -m "feat: add example timeline YAML files"
```

---

## Task 16: Docker Compose and justfile updates

**Files:**
- Modify: `$BASE/docker-compose.yml`
- Modify: `$BASE/justfile`

- [ ] **Step 1: Update docker-compose.yml generator command**

Update the `generator` service in `$BASE/docker-compose.yml`:
- Mount `./timelines:/timelines:ro`
- Change command to use `--timeline /timelines/quick-test.yaml`

```yaml
generator:
    build:
      context: ./generator
    depends_on:
      - influxdb
      - timescaledb-metrics
    environment:
      INFLUXDB_URL: http://influxdb:8086
      INFLUXDB_TOKEN: tropek-dev-token
      INFLUXDB_ORG: tropek
      INFLUXDB_BUCKET: slo_metrics
      TIMESCALEDB_DSN: postgresql://metrics:metrics@timescaledb-metrics:5432/slo_metrics
    command:
      - "--timeline"
      - "/timelines/quick-test.yaml"
      - "--backends"
      - "prometheus"
      - "--backends"
      - "influxdb"
      - "--backends"
      - "timescaledb"
      - "--run-promtool"
      - "--prometheus-data-dir"
      - "/prometheus"
    volumes:
      - prometheus-data:/prometheus
      - ./timelines:/timelines:ro
```

- [ ] **Step 2: Update justfile with timeline recipes**

Add new recipes to `$BASE/justfile`:

```just
# Generate timeline data locally as CSV (for inspection)
gen-timeline timeline:
    uv run --directory generator slo-generate \
        --timeline {{timeline}} \
        --backends csv \
        --output-dir ./output
```

- [ ] **Step 3: Commit**

```
git -C .worktrees/generator-refactor add $BASE/docker-compose.yml $BASE/justfile
git -C .worktrees/generator-refactor commit -m "feat: update docker-compose and justfile for timeline mode"
```

---

## Task 17: Update CLAUDE.md documentation

**Files:**
- Modify: `$BASE/CLAUDE.md`

- [ ] **Step 1: Update CLAUDE.md**

Update `$BASE/CLAUDE.md` to document:
- Timeline mode in Common Commands (`just gen-timeline timelines/quick-test.yaml`)
- The `--timeline` CLI flag
- Timeline YAML format brief reference
- The `timelines/` directory

Add a `## Timeline Mode` section after the existing `## Common Commands`:

```markdown
## Timeline Mode

Generate composed timelines with events placed at specific timestamps:

```bash
just gen-timeline timelines/quick-test.yaml        # CSV output for inspection
just gen-timeline timelines/evaluation-30d.yaml     # 30-day quality gate test
just gen-timeline timelines/change-detection-60d.yaml  # change point detection
```

Timeline YAML files define a healthy baseline with events spliced in:

```yaml
timeline:
  start: "2026-03-14T00:00:00Z"
  duration: 168h
  resolution: 30s
  events:
    - type: outage
      at: 160h
      duration: 30m
      resolution: 5s
```

Available event types: `outage`, `degradation`, `memory_leak`, `traffic_spike`,
`step_change`, `polska`.
```

- [ ] **Step 2: Commit**

```
git -C .worktrees/generator-refactor add $BASE/CLAUDE.md
git -C .worktrees/generator-refactor commit -m "docs: update CLAUDE.md with timeline mode"
```

---

## Task 18: Final verification — all tests pass

- [ ] **Step 1: Run full test suite**

Run: `uv run --directory $GEN pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 2: Verify CSV generation with quick-test timeline**

Run: `uv run --directory $GEN slo-generate --timeline $BASE/timelines/quick-test.yaml --backends csv --output-dir /tmp/timeline-test`
Expected: CSV files generated in `/tmp/timeline-test/timeline/`

- [ ] **Step 3: Verify metadata.json is written**

Check: `/tmp/timeline-test/timeline/metadata.json` exists and contains valid JSON with
`start`, `end`, `events`, and `generated_at` fields.

- [ ] **Step 4: Verify backward compatibility**

Run: `uv run --directory $GEN slo-generate --scenarios healthy --hours 1 --backends csv --output-dir /tmp/legacy-test`
Expected: CSV files generated (legacy mode still works)
