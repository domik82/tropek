# Timeline Composer — Design Spec

> **Status:** Draft
> **Date:** 2026-03-21
> **Author:** Dominik + Claude
> **Builds on:** [Generator Refactor](2026-03-20-generator-refactor-design.md)

---

## 1. Problem Statement

The generator refactor (completed) creates a clean Scenario → Shaper → Adapter pipeline,
but the CLI treats scenarios as independent full-timeline generators. All three scenarios
(healthy, outage, degradation) get the same `start→end` window, write to the same metric
names with the same labels, and overwrite each other's data.

For tropek's quality gate evaluation, we need:

- **30–90 days of continuous data** with a healthy baseline showing diurnal patterns
- **Events placed at specific timestamps** (outages, degradations, memory leaks, traffic spikes)
- **Realistic transitions** between states (instant blue/green switch or brief restart gap)
- **Variable resolution** — coarse (30s) for baseline, fine (1s–5s) for incident windows
- **Docker-friendly data volumes** — 60 days at 30s resolution ≈ 170K rows per service-host,
  not 5.2M at 1s
- **Dashboards that show the data immediately** when Grafana starts — no manual time picker

### Additional Scenarios Needed

The existing three scenarios (healthy, outage, degradation) cover basic cases.
For change point detection algorithm testing and realistic simulation, we need:

- **Memory leak** — exponential latency growth over days/weeks, ending in crash
- **Traffic spike** — sudden burst causing 429 rate-limiting or 5xx overload
- **Step change** — sustained level shift (new baseline after config change or capacity reduction)
- **Polska** — easter egg scenario using Poland's geographic contour as metric envelope

## 2. Goals

- YAML-based timeline composition — repeatable, version-controllable, parameterizable
- Cut-and-paste model: healthy baseline fills the full range, events replace windows
- Backward compatibility: `--scenarios` mode still works for quick one-offs
- No changes to shapers or adapters — they receive the same profile chunks as before
- Dashboard auto-ranges to show last 7 days of generated data

## 3. Architecture

### Current Flow (per-scenario, independent)

```
CLI --scenarios healthy outage degradation
  └─ for each scenario:
       Scenario(start, end) → chunks → Shaper → Adapter
```

### New Flow (timeline composition)

```
CLI --timeline timeline.yaml
  └─ TimelineComposer(yaml)
       ├─ HealthyScenario(full range) → baseline chunks
       ├─ EventScenario(event window) → event chunks
       └─ splice: replace baseline rows with event rows, apply gaps
            └─ unified chunks → Shaper → Adapter
```

The `TimelineComposer` implements the same interface as `BaseScenario` — it yields
profile DataFrame chunks. The pipeline below (shapers, adapters) is unchanged.

### Data Flow Detail

```
TimelineComposer.generate(resolution_seconds)
  │
  ├─ 1. Parse timeline YAML → list of EventSpec
  ├─ 2. Sort events by start time, validate no overlaps
  ├─ 3. Iterate hour-sized time windows:
  │      a. Generate healthy baseline chunk for this window
  │      b. For each event overlapping this window:
  │         - Generate event scenario chunk for the overlap
  │         - Replace matching rows in the baseline chunk
  │      c. Apply restart_gap: drop rows in gap windows
  │      d. Apply per-event resolution override (if coarser than baseline,
  │         handled by generating fewer timestamps for that window)
  │      e. Yield the composed chunk
  │
  └─ 4. After all chunks: write metadata JSON (start, end, events summary)
```

### Resolution Strategy

The timeline has a global `resolution` (default `30s`). Events can override with
a finer resolution. The composer handles this by:

1. For time windows with no events: generate at global resolution
2. For time windows containing an event with finer resolution: generate at the
   event's resolution for the overlap, global resolution for the rest
3. Shapers downstream handle whatever resolution they receive (PrometheusShaper
   already downsamples to scrape_interval; InfluxDB/TimescaleDB pass through)

This means a 60-day timeline at 30s with a 30-minute outage at 1s produces:
- ~170K baseline rows + ~10.8K event rows per service-host combo
- Total ≈ 1.1M rows across 6 combos — Docker-safe

## 4. Timeline YAML Format

```yaml
# timeline.yaml — example: 60 days healthy, memory leak at day 40, outage at day 59
timeline:
  start: 2026-01-20T00:00:00Z   # absolute start time
  duration: 1440h                # 60 days (required if no 'end')
  # end: 2026-03-21T00:00:00Z   # alternative to duration
  resolution: 30s                # global baseline resolution (default: 30s)
  baseline: healthy              # scenario used for gaps between events (default: healthy)

  events:
    - type: memory_leak
      at: 960h                   # offset from start (day 40)
      duration: 456h             # 19 days of slow degradation, then crash
      params:                    # scenario-specific parameters
        growth_rate: 0.003       # exponential growth constant
        crash_at_end: true

    - type: outage
      at: 1416h                  # day 59
      duration: 30m
      restart_gap: 0s            # blue/green deploy — instant switch (default: 0s)
      resolution: 1s             # fine resolution for this event only

    - type: traffic_spike
      at: 720h                   # day 30
      duration: 2h
      params:
        spike_multiplier: 8.0
        error_mode: rate_limit   # "rate_limit" (429) or "overload" (5xx)
      resolution: 5s

    - type: step_change
      at: 480h                   # day 20
      duration: 240h             # permanent: runs until next event or end
      params:
        latency_multiplier: 1.8
        throughput_multiplier: 0.7
```

### YAML Schema

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `timeline.start` | ISO 8601 datetime | yes | — | Absolute start time |
| `timeline.duration` | duration string | one of duration/end | — | Total timeline length |
| `timeline.end` | ISO 8601 datetime | one of duration/end | — | Absolute end time |
| `timeline.resolution` | duration string | no | `30s` | Global baseline resolution |
| `timeline.baseline` | string | no | `healthy` | Scenario for gaps between events |
| `events[].type` | string | yes | — | Scenario name (registered in factory) |
| `events[].at` | duration string | yes | — | Offset from timeline start |
| `events[].duration` | duration string | yes | — | How long the event lasts |
| `events[].restart_gap` | duration string | no | `0s` | Data gap after event ends (simulates restart) |
| `events[].resolution` | duration string | no | global | Resolution override for this event |
| `events[].params` | dict | no | `{}` | Scenario-specific parameters |

Duration strings support: `s` (seconds), `m` (minutes), `h` (hours), `d` (days).
Examples: `30s`, `5m`, `2h`, `720h`, `30d`.

### Validation Rules

1. `start` is required and must be a valid UTC datetime
2. Exactly one of `duration` or `end` must be provided
3. Events must not overlap (error if two events cover the same time window)
4. Event `at + duration` must not exceed the timeline's total duration
5. Event `type` must be a registered scenario name
6. Event `resolution` must be ≤ global `resolution` (finer, not coarser)

## 5. Scenario Changes

### Existing Scenarios — Refactored

The existing scenarios (outage, degradation) have hardcoded phase offsets like
"outage starts at 60% of the time range." With timeline composition, the event
window IS the event — no pre-event healthy phase needed.

**Change:** Add an `event_mode` flag to `BaseScenario.__init__` (default `False`),
stored as `self.event_mode`. Subclasses check this flag to adjust phase offsets.

When `event_mode=True`:
- The scenario fills its entire `start→end` window with the event behavior
- No "pre-event healthy phase" — the composer handles that
- Ramp-in starts at `start`, ramp-out/recovery ends at `end`

When `event_mode=False` (default, backward compatible):
- Current behavior preserved — standalone mode with internal phase offsets

```python
class BaseScenario(ABC):
    def __init__(self, start, end, *, event_mode=False):
        self.start = start
        self.end = end
        self.event_mode = event_mode
        self._rng = np.random.default_rng(seed=42)

class OutageScenario(BaseScenario):
    def __init__(self, start, end, *, event_mode=False, recovery_minutes=10, ...):
        super().__init__(start, end, event_mode=event_mode)
        if event_mode:
            self.outage_start = start
            self.outage_end = end - timedelta(minutes=recovery_minutes)
            self.recovery_end = end
        else:
            # existing behavior: outage at 60% mark
            ...
```

**DegradationScenario event_mode:** The ramp starts at `start`, degraded level holds
through `end`. No recovery phase — the composer handles the transition back to healthy
when the event window ends.

### New Scenarios

All new scenarios are event-only — they have no standalone mode. They always fill
their entire time window with the event pattern.

#### MemoryLeakScenario

Simulates a slow resource leak that degrades performance over days/weeks until crash.

**Parameters:**
- `growth_rate` (float, default 0.003) — exponential growth constant
- `crash_at_end` (bool, default True) — simulate OOM crash in final hour

**Behavior:**
- Latency: `base * (1 + growth_rate * exp(t / tau))` where `tau` scales to fill the duration
- Memory: linear growth from 512MB toward 95% of capacity
- Throughput: gradual decrease as GC pressure increases
- Error rate: stays low until final phase, then spikes
- If `crash_at_end`: final hour shows OOM pattern (throughput → 0, errors → 1.0, latency → timeout)

**Profile shape** (referencing the wear process / divergent wear screenshots):
```
latency
  │                                          ╱
  │                                        ╱
  │                                     ╱
  │                                  ╱
  │                              _╱
  │                          _╱
  │                     __╱
  │              ____╱
  │     ________╱
  └──────────────────────────────────────── time
  day 1                                   day 19
```

#### TrafficSpikeScenario

Simulates a sudden burst of traffic from an external event (viral post, bot attack, etc.).

**Parameters:**
- `spike_multiplier` (float, default 5.0) — peak traffic as multiple of baseline
- `error_mode` (str, default "rate_limit") — either `"rate_limit"` (429 errors, low latency)
  or `"overload"` (5xx errors, high latency)
- `ramp_minutes` (int, default 5) — time to reach peak
- `sustain_fraction` (float, default 0.6) — fraction of duration at peak before tapering

**Behavior — rate_limit mode:**
- Throughput: ramps to `base * spike_multiplier`, sustains, then tapers
- Error rate: rises proportional to traffic above capacity threshold (~2x baseline)
- Latency: stays near baseline (rate limiter rejects fast)
- Status codes: excess traffic returns 429

**Behavior — overload mode:**
- Throughput: ramps up, then collapses under load (throughput drops as system saturates)
- Error rate: rises sharply (5xx from timeouts, connection exhaustion)
- Latency: spikes dramatically (queuing, thread starvation)
- CPU: hits 100%

#### StepChangeScenario

Simulates a sustained level shift — after a config change, capacity reduction, or
infrastructure migration, metrics settle at a new baseline. To simulate a truly
permanent shift, set `duration` to span from the event start to the timeline end.

**Parameters:**
- `latency_multiplier` (float, default 1.5) — new latency level as multiple
- `throughput_multiplier` (float, default 1.0) — new throughput level
- `error_rate_multiplier` (float, default 1.0) — new error rate level
- `ramp_minutes` (int, default 2) — transition time to new level

**Behavior:**
- Brief ramp (default 2 min) from old baseline to new level
- Then flat at new level for the rest of the duration
- The new level persists until the event ends (composer switches back to healthy)

This is useful for testing change point detection: can the algorithm detect a 20%
latency increase that happens gradually over 2 minutes and then stays?

#### PolskaScenario (Easter Egg)

Generates metric curves whose envelope traces the geographic outline of Poland.

**Implementation approach:**
- Store Poland's border as a normalized coordinate array (x=0..1, y=0..1)
- Map x-axis to the event's time window
- Map y-axis to metric value range
- Top contour → throughput envelope (higher values = more traffic)
- Bottom contour (inverted) → response time envelope
- Add realistic noise within the envelope (gaussian jitter)
- The two metrics are naturally anti-correlated (Poland's shape widens/narrows)

**Parameters:**
- `noise_amplitude` (float, default 0.05) — noise as fraction of envelope height
- `throughput_range` (tuple, default (50, 200)) — min/max throughput
- `latency_range` (tuple, default (0.01, 0.5)) — min/max latency

**Visual result** (conceptual):
```
throughput                         ___________
  200 │          __________________╱           ╲____
      │    _____╱                                   ╲___
      │___╱                                             ╲
   50 │────────────────────────────────────────────────────
      │                                               ___╱
      │___                                       ____╱
latency╲  ╲_____                          ______╱
  0.5 │         ╲________________________╱
      └──────────────────────────────────────────────── time
```

The contour data will be stored as a numpy array in `scenarios/polska_contour.py`,
extracted from a simplified SVG of Poland's border (~200 coordinate pairs).

## 6. TimelineComposer

### BaseScenario: `generate_window` Method

To support the composer extracting data for arbitrary sub-windows at specific
resolutions, `BaseScenario` gets a new public method:

```python
class BaseScenario(ABC):
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
            window_start, window_end,
            freq=f"{resolution_seconds}s", inclusive="left", tz="UTC",
        ).as_unit("ns")
        if len(timestamps) == 0:
            return pd.DataFrame(columns=PROFILE_COLUMNS)
        return self._build_chunk(timestamps)
```

This reuses the existing `_build_chunk` / `_build_profiles` machinery without
breaking encapsulation. The composer calls `generate_window` for event overlaps
instead of iterating `generate()`.

### Interface

```python
class TimelineComposer:
    """Composes a continuous timeline from a healthy baseline + event splices."""

    def __init__(self, config: TimelineConfig):
        self.config = config

    def generate(
        self,
        resolution_seconds: int = 30,
        chunk_hours: int = 1,
    ) -> Iterator[pd.DataFrame]:
        """Yield composed profile DataFrame chunks.

        resolution_seconds is taken from self.config, not from the parameter
        (kept in signature for interface compatibility with pipeline).
        """
        ...

    @classmethod
    def from_yaml(cls, path: Path) -> TimelineComposer:
        """Load a timeline from a YAML file."""
        ...
```

The composer duck-types with `BaseScenario` — it has `generate()` that yields
profile DataFrames. The pipeline code doesn't need to know whether it's getting
chunks from a single scenario or a composed timeline.

### TimelineConfig

```python
@dataclass
class EventSpec:
    type: str
    at: timedelta           # offset from timeline start
    duration: timedelta
    restart_gap: timedelta  # default 0s
    resolution: int | None  # seconds, None = use global
    params: dict[str, Any]  # scenario-specific parameters

@dataclass
class TimelineConfig:
    start: datetime
    end: datetime
    resolution_seconds: int       # global (default 30)
    baseline: str                 # scenario name (default "healthy")
    events: list[EventSpec]
```

### Composition Algorithm

```python
def generate(self, resolution_seconds, chunk_hours=1):
    # resolution_seconds parameter is ignored — we use self.config.resolution_seconds
    # (kept in signature for interface compatibility)

    baseline = get_scenario(self.config.baseline, start=self.config.start, end=self.config.end)

    # Pre-build event scenarios (with event_mode=True)
    event_scenarios = []
    for event in sorted(self.config.events, key=lambda e: e.at):
        event_start = self.config.start + event.at
        event_end = event_start + event.duration
        scenario = get_scenario(event.type, start=event_start, end=event_end,
                                event_mode=True, **event.params)
        event_scenarios.append((event, scenario, event_start, event_end))

    # Iterate in hour-sized windows
    chunk_start = self.config.start
    chunk_delta = timedelta(hours=chunk_hours)

    while chunk_start < self.config.end:
        chunk_end = min(chunk_start + chunk_delta, self.config.end)

        # Find events overlapping this chunk
        overlapping = [(ev, sc, es, ee) for ev, sc, es, ee in event_scenarios
                       if es < chunk_end and ee > chunk_start]

        if not overlapping:
            # Pure baseline chunk — use generate_window at global resolution
            yield baseline.generate_window(
                chunk_start, chunk_end, self.config.resolution_seconds)
        else:
            # Composed chunk: baseline + event splices
            chunk = baseline.generate_window(
                chunk_start, chunk_end, self.config.resolution_seconds)

            for event, scenario, ev_start, ev_end in overlapping:
                # Overlap boundaries within this chunk
                overlap_start = max(chunk_start, ev_start)
                overlap_end = min(chunk_end, ev_end)
                ev_resolution = event.resolution or self.config.resolution_seconds

                # Generate event data for the overlap window
                event_data = scenario.generate_window(
                    overlap_start, overlap_end, ev_resolution)

                # Replace: drop baseline rows in the overlap, concat event rows
                chunk = chunk[
                    (chunk["timestamp"] < overlap_start) |
                    (chunk["timestamp"] >= overlap_end)
                ]
                chunk = pd.concat([chunk, event_data], ignore_index=True)

                # Apply restart gap (drop rows after event ends)
                if event.restart_gap.total_seconds() > 0:
                    gap_end = overlap_end + event.restart_gap
                    chunk = chunk[
                        (chunk["timestamp"] < overlap_end) |
                        (chunk["timestamp"] >= gap_end)
                    ]

            chunk = chunk.sort_values("timestamp").reset_index(drop=True)
            yield chunk

        chunk_start = chunk_end
```

### Gap Handling

Restart gaps are handled inline in the composition algorithm (see above): rows in the
gap window are dropped from the composed DataFrame. Default `restart_gap: 0s` means
instant blue/green switch — no data loss.

Missing rows in the profile DataFrame propagate naturally through shapers:
- PrometheusShaper: gap in counter accumulation = no data points (realistic scrape gap)
- InfluxDB/TimescaleDB: missing timestamps = no rows written (realistic outage gap)
- Grafana: shows gap in graph (exactly what you'd see in production during a restart)

## 7. CLI Changes

### New `--timeline` Flag

```python
@click.command()
@click.option("--timeline", type=click.Path(exists=True, path_type=Path),
              help="Timeline YAML file for composed generation")
# ... existing options preserved ...
def main(timeline, scenarios, backends, hours, resolution, ...):
    if timeline:
        composer = TimelineComposer.from_yaml(timeline)
        start, end = composer.config.start, composer.config.end
        resolution = composer.config.resolution_seconds
        scenario_source = composer
        scenario_name = "timeline"
    else:
        # existing per-scenario loop (backward compatible)
        end = datetime.now(tz=UTC)
        start = end - timedelta(hours=hours)
        for scenario_name in scenarios:
            scenario = get_scenario(scenario_name, start=start, end=end)
            run_pipeline(scenario=scenario, ...)
        return

    results = run_pipeline(
        scenario=scenario_source,
        backends=list(backends),
        output_dir=output_dir / scenario_name,
        scenario_name=scenario_name,
        resolution_seconds=resolution,
        ...
    )
```

### Metadata Output

After `run_pipeline` completes, the **CLI** writes a `metadata.json` to `output_dir`.
This keeps I/O out of the composer (which is a generator) and out of the pipeline
(which shouldn't know about timelines):

```json
{
  "start": "2026-01-20T00:00:00Z",
  "end": "2026-03-21T00:00:00Z",
  "resolution_seconds": 30,
  "events": [
    {"type": "memory_leak", "start": "2026-02-28T00:00:00Z", "end": "2026-03-19T00:00:00Z"},
    {"type": "outage", "start": "2026-03-19T00:00:00Z", "end": "2026-03-19T00:30:00Z"}
  ],
  "generated_at": "2026-03-21T10:00:00Z"
}
```

This file is used by the dashboard generator to set the correct time range.

## 8. Dashboard Time Range

### Problem

Current dashboard config has `time_from: "now-1h"`, `time_to: "now"`. Historical
data (e.g., ending at 2026-03-21T00:00Z) won't be visible when you open Grafana.

### Solution

The dashboard generator reads the metadata JSON (if it exists) and sets the dashboard
time range to show the last 7 days of generated data:

```python
def get_time_range(metadata_path: Path) -> tuple[str, str]:
    """Return Grafana time range showing last 7 days of generated data."""
    if metadata_path.exists():
        meta = json.loads(metadata_path.read_text())
        end = datetime.fromisoformat(meta["end"])
        start = end - timedelta(days=7)
        return start.isoformat() + "Z", end.isoformat() + "Z"
    return "now-1h", "now"  # fallback for live scrape mode
```

The dashboard YAML config gets updated:
```yaml
time_from: "{{ time_from }}"  # set by generate_dashboard.py
time_to: "{{ time_to }}"
```

When the generator runs in Docker Compose, the sequence is:
1. Generator produces data + writes `metadata.json`
2. Dashboard generator reads `metadata.json`, renders dashboards with correct time range
3. Grafana loads dashboards — data is visible immediately

### Docker Compose Ordering

```yaml
generator:
  # ... existing config ...
  # writes metadata.json to shared volume

dashboard-gen:
  build:
    context: ./grafana
  depends_on:
    generator:
      condition: service_completed_successfully
  volumes:
    - ./grafana:/grafana
    - generator-output:/output:ro
  command: ["python", "generate_dashboard.py", "--metadata", "/output/metadata.json"]
```

Alternatively (simpler): the generator itself calls the dashboard generation after
completing data generation, since both run in the same container context. The metadata
file is just a local path.

## 9. Package Structure Changes

```
generator/src/slo_generator/
├── cli.py                        # +--timeline flag, backward compat
├── pipeline.py                   # unchanged
├── constants.py                  # unchanged
├── composer.py                   # NEW: TimelineComposer + TimelineConfig + YAML parsing
├── scenarios/
│   ├── __init__.py               # factory updated with new scenarios
│   ├── base.py                   # +event_mode support
│   ├── healthy.py                # unchanged
│   ├── outage.py                 # +event_mode
│   ├── degradation.py            # +event_mode
│   ├── csv_input.py              # unchanged
│   ├── memory_leak.py            # NEW
│   ├── traffic_spike.py          # NEW
│   ├── step_change.py            # NEW
│   ├── polska.py                 # NEW (easter egg)
│   └── polska_contour.py         # NEW (coordinate data)
├── shapers/                      # unchanged
└── adapters/                     # unchanged

generator/tests/
├── conftest.py                   # +timeline fixtures
├── test_scenarios.py             # +new scenario tests
├── test_composer.py              # NEW: timeline composition tests
├── test_shapers.py               # unchanged
├── test_adapters.py              # unchanged
└── test_pipeline.py              # +timeline integration test

timelines/                        # NEW: example timeline YAML files
├── quick-test.yaml               # 7 days, one outage (fast Docker test)
├── evaluation-30d.yaml           # 30 days, outage at end
├── change-detection-60d.yaml     # 60 days, memory leak + step change
└── easter-egg.yaml               # polska scenario
```

## 10. Example Timeline Files

### quick-test.yaml (Docker default — fast)

```yaml
timeline:
  start: 2026-03-14T00:00:00Z
  duration: 168h               # 7 days
  resolution: 30s
  baseline: healthy

  events:
    - type: outage
      at: 160h                 # near the end
      duration: 30m
      resolution: 5s
```

### evaluation-30d.yaml (Quality gate testing)

```yaml
timeline:
  start: 2026-02-19T00:00:00Z
  duration: 720h               # 30 days
  resolution: 30s
  baseline: healthy

  events:
    - type: degradation
      at: 504h                 # day 21
      duration: 4h
      params:
        latency_multiplier: 3.0
        error_rate_multiplier: 2.0

    - type: outage
      at: 690h                 # day 28.75
      duration: 45m
      resolution: 1s
      restart_gap: 30s
```

### change-detection-60d.yaml (Change point detection testing)

```yaml
timeline:
  start: 2026-01-20T00:00:00Z
  duration: 1440h              # 60 days
  resolution: 30s
  baseline: healthy

  events:
    - type: step_change
      at: 480h                 # day 20: permanent level shift
      duration: 240h           # 10 days at new level
      params:
        latency_multiplier: 1.3
        throughput_multiplier: 0.85

    - type: memory_leak
      at: 960h                 # day 40: slow leak starts
      duration: 336h           # 14 days until crash
      params:
        growth_rate: 0.005
        crash_at_end: true

    - type: traffic_spike
      at: 1380h                # day 57.5: sudden spike
      duration: 3h
      params:
        spike_multiplier: 6.0
        error_mode: overload
      resolution: 5s
```

## 11. Docker Compose Changes

### Updated Generator Command

```yaml
generator:
  build:
    context: ./generator
  depends_on:
    influxdb:
      condition: service_healthy
    timescaledb-metrics:
      condition: service_healthy
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

### Updated Justfile

```just
# Generate with default timeline (7-day quick test)
up: dashboard
    docker compose up --build -d

# Generate with a specific timeline
up-timeline timeline='timelines/quick-test.yaml':
    TIMELINE={{timeline}} docker compose up --build -d

# Generate timeline data locally as CSV (for inspection)
gen-timeline timeline:
    uv run --directory generator slo-generate \
        --timeline {{timeline}} \
        --backends csv \
        --output-dir ./output
```

## 12. Shaper State and Timeline Continuity

The timeline composer yields chunks in chronological order. Stateful shapers
(PrometheusShaper with cumulative counters) naturally handle this — they accumulate
across chunks regardless of whether the chunk came from baseline or an event splice.

When a restart gap is present (missing rows):
- Counter accumulators freeze during the gap
- When data resumes, counters continue from where they left off
- This is exactly what Prometheus sees during a real pod restart — a gap followed
  by counters continuing (or resetting to 0 for a true restart)

For a true restart simulation (counter reset to 0), the composer could optionally
reset the shaper's accumulators. This is a future enhancement — not needed for v1.

## 13. What Changes vs. What Stays

### Changed

| Component | Change |
|---|---|
| `cli.py` | Add `--timeline` flag, conditional dispatch |
| `scenarios/base.py` | Add `event_mode` parameter support |
| `scenarios/outage.py` | Support `event_mode=True` (outage fills entire window) |
| `scenarios/degradation.py` | Support `event_mode=True` |
| `scenarios/__init__.py` | Register new scenarios in factory |
| `grafana/generate_dashboard.py` | Read metadata JSON for time range |
| `grafana/dashboard_config.yaml` | Dynamic time_from/time_to |
| `docker-compose.yml` | Updated generator command for timeline mode |
| `justfile` | New timeline-related recipes |

### New

| Component | Purpose |
|---|---|
| `composer.py` | TimelineComposer + TimelineConfig + YAML parser |
| `scenarios/memory_leak.py` | Exponential degradation scenario |
| `scenarios/traffic_spike.py` | Sudden burst scenario |
| `scenarios/step_change.py` | Permanent level shift scenario |
| `scenarios/polska.py` | Easter egg scenario |
| `scenarios/polska_contour.py` | Poland border coordinates |
| `tests/test_composer.py` | Timeline composition tests |
| `timelines/*.yaml` | Example timeline files |

### Unchanged

| Component | Why |
|---|---|
| `shapers/*` | Receive same profile DataFrames as before |
| `adapters/*` | Receive same shaped DataFrames as before |
| `pipeline.py` | Receives chunks from composer instead of scenario — same interface |
| `constants.py` | No new constants needed |
| `scenarios/healthy.py` | No changes (no event_mode needed — it's always "healthy") |
| `scenarios/csv_input.py` | Standalone, no event_mode needed |

## 14. Dependencies

One new dependency: `pyyaml>=6.0` must be added to `pyproject.toml` for timeline
YAML parsing. Click does not bundle PyYAML.

## 15. Non-Goals

- **Overlapping events** — events must not overlap in v1 (validation error)
- **Shaper counter resets** — true restart simulation (counter → 0) is a future enhancement
- **Parallel scenario generation** — single-threaded is sufficient
- **Real-time streaming** — this is a batch data generator, not a live exporter
- **Arbitrary metric names/labels** — we generate the fixed set from constants.py
- **GUI/TUI for timeline editing** — YAML files are the interface
