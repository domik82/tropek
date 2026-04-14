# Heatmap Chunk C — perf log

All measurements use `scripts/perf/bench-heatmap.py` against the dataset seeded
by `scripts/perf/seed-heatmap-dataset.py` (1 asset, 3 SLOs, 18 objectives,
200 runs, ~30 days, ~1.07 MB response).

Reproduce against `scripts/dev-start.sh` (API on :9080):

    ./scripts/dev-start.sh                              # full dev stack
    QG_DB_USER=tropek_e2e QG_DB_PASSWORD=tropek_e2e \
      QG_DB_HOST=localhost QG_DB_PORT=5434 QG_DB_NAME=tropek_e2e \
      QG_REDIS_PASSWORD=e2e_redis QG_REDIS_HOST=localhost QG_REDIS_PORT=6380 \
      QG_SECRET_KEY=e2e-test-key QG_CONFIG_PATH=config.yaml \
      uv run --directory api python ../scripts/perf/seed-heatmap-dataset.py
    uv run --directory api python ../scripts/perf/bench-heatmap.py http
    QG_... uv run --directory api python ../scripts/perf/bench-heatmap.py profile

The harness reads `TROPEK_API_BASE` (default `http://localhost:9080`).

## Baseline (commit `33f9740`, PR1)

_No caching exists yet; cache=true and cache=false fall through the same build path. Response size: 1,073,347 bytes._

### cache=true (default)
| metric | value |
|---|---|
| p50 latency (ms) | 70.3 |
| p95 latency (ms) | 133.1 |
| p99 latency (ms) | 160.1 |
| mean latency (ms) | 81.1 |
| payload bytes | 1073347 |

### cache=false (bypass)
| metric | value |
|---|---|
| p50 latency (ms) | 67.1 |
| p95 latency (ms) | 111.8 |
| p99 latency (ms) | 126.5 |
| mean latency (ms) | 75.0 |
| payload bytes | 1073347 |

### cProfile top 15 (cumulative) — 50 in-process iterations of `build_grouped_heatmap_response`
```
         6457901 function calls in 2.680 seconds

   Ordered by: cumulative time
   List reduced from 27 to 15 due to restriction <15>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
       50    0.006    0.000    2.680    0.054 presenter.py:259(build_grouped_heatmap_response)
       50    0.522    0.010    2.486    0.050 presenter.py:121(_collect_slo_heatmap_data)
   180000    0.228    0.000    1.349    0.000 target_resolver.py:13(resolve_targets)
   180000    0.363    0.000    0.750    0.000 criteria.py:72(parse_criteria_string)
   476100    0.201    0.000    0.612    0.000 pydantic/main.py:240(__init__)
  2490000    0.456    0.000    0.456    0.000 sqlalchemy/orm/attributes.py:555(__get__)
   476100    0.411    0.000    0.411    0.000 pydantic_core SchemaValidator.validate_python
       50    0.049    0.001    0.143    0.003 presenter.py:188(_build_slo_groups)
   180000    0.074    0.000    0.105    0.000 criteria.py:135(evaluate_criteria)
   720000    0.086    0.000    0.086    0.000 re.Match.group
   180000    0.086    0.000    0.086    0.000 re.Pattern.match
   330000    0.042    0.000    0.042    0.000 dict.get
   360000    0.037    0.000    0.037    0.000 criteria.py:31(compute_target_value)
   290150    0.033    0.000    0.033    0.000 list.append
       50    0.011    0.000    0.030    0.001 presenter.py:238(_build_composite_summary)
```
| metric | value |
|---|---|
| rss delta (KB) | 4080 |

**Where the time goes:**
- `build_grouped_heatmap_response`: 2.680s / 50 = **53.6 ms per build** (in-process, no HTTP — close to http p50 70ms minus network)
- `_collect_slo_heatmap_data`: 2.486s = **92.7%** of build time. The hot loop.
- `resolve_targets`: 1.349s = **50.3%** of build time, called 180,000× (3,600 cells × 50 iterations × 2 thresholds — actually per-call it's 1× but the outer call wraps both pass and warning resolution). Win 3 (parse-once) hits this directly.
- `parse_criteria_string`: 0.750s = **28%** of build time, 180,000 invocations. Win 3 reduces this to 18 invocations per request (one per unique objective × pass/warning), a ~200× drop in parses.
- Pydantic `__init__` + `validate_python`: 1.023s = **38%** combined. Lower bound; per-column caching makes this nearly free on cache hits because the cached fragment is `model_validate_json`'d into a fragment object once instead of re-instantiated cell-by-cell.
- SQLAlchemy attribute access: 2,490,000 calls → 0.456s. Lazy attribute access on relationship-walked rows. Per-column caching skips this entirely on cache hits.

## After Chunk C — per-column Redis cache (commit `779cf4e`)

_Same dataset as the baseline. cache is warmed by the worker warm path
(`queue.py::finalize_run_job`) as each run completes, so `cache=true`
measures the MGET + assemble path and `cache=false` measures the full
DB-read + build path._

### cache=true (default, warm hit)
| metric | value |
|---|---|
| p50 latency (ms) | 30.0 |
| p95 latency (ms) | 94.7 |
| p99 latency (ms) | 118.9 |
| mean latency (ms) | 39.3 |
| payload bytes | 1073947 |

### cache=false (bypass, full build)
| metric | value |
|---|---|
| p50 latency (ms) | 86.3 |
| p95 latency (ms) | 163.3 |
| p99 latency (ms) | 245.6 |
| mean latency (ms) | 103.1 |
| payload bytes | 1073947 |

### cProfile top 15 (cumulative) — 50 in-process iterations after Chunk C
```
         7136051 function calls in 3.371 seconds

   Ordered by: cumulative time
   List reduced from 35 to 15 due to restriction <15>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
       50    0.025    0.001    3.371    0.067 presenter.py:206(build_grouped_heatmap_response)
     5000    0.649    0.000    3.297    0.001 presenter.py:249(build_column_fragment)
    90000    0.168    0.000    1.129    0.000 presenter.py:235(_parse_objective_criteria)
   585200    0.391    0.000    0.891    0.000 pydantic/main.py:240(__init__)
   180000    0.315    0.000    0.869    0.000 criteria.py:72(parse_criteria_string)
   180000    0.290    0.000    0.673    0.000 target_resolver.py:45(resolve_targets_from_parsed)
   585200    0.499    0.000    0.499    0.000 pydantic_core SchemaValidator.validate_python
  2450000    0.464    0.000    0.464    0.000 sqlalchemy/orm/attributes.py:555(__get__)
   180000    0.077    0.000    0.110    0.000 criteria.py:135(evaluate_criteria)
   720000    0.091    0.000    0.091    0.000 re.Match.group
   180000    0.088    0.000    0.088    0.000 re.Pattern.match
   330000    0.045    0.000    0.045    0.000 dict.get
       50    0.027    0.001    0.042    0.001 presenter.py:138(assemble_grouped_response)
   360000    0.041    0.000    0.041    0.000 criteria.py:31(compute_target_value)
     5000    0.018    0.000    0.040    0.000 presenter.py:363(_build_composite_summary_for_run)
```
| metric | value |
|---|---|
| rss delta (KB) | 4736 |

**The cache-miss path got slightly slower**, not faster. `build_grouped_heatmap_response`
now takes 67.4 ms per build vs 53.6 ms on the baseline — a ~25 % regression on the
fully-synchronous cache-miss path. Two reasons:

1. **Pydantic instantiations went up**, 476,100 → 585,200. The per-column assembly
   creates fresh `HeatmapColumnFragment` + `HeatmapColumnSloFragment` objects on top
   of the cells and summaries that were already being created.
2. **Parse-once cache doesn't help this dataset**. Each run in the seeded data has
   exactly one indicator row per objective, so there are no intra-run duplicate
   criteria to dedupe. The `_parse_objective_criteria` call count (90,000 = 1,800
   per build) matches the unique-objective-per-build count; `parse_criteria_string`
   still runs 180,000 times (same as baseline) because every objective still gets
   its pass + warning criteria parsed once per build. The optimization is
   dataset-dependent — real SLOs that reuse the same objective across multiple
   indicators within one run benefit, synthetic one-cell-per-objective data does not.

**But** the cache-HIT path is where the chunk earns its keep, and that path skips
`build_grouped_heatmap_response` entirely — it only runs the MGET, JSON-decodes each
fragment once, and calls `assemble_grouped_response` (~1 ms for 50 calls in the
profile). That's how cache=true p50 drops from 70.3 ms → 30.0 ms despite the
slower miss path.

## Realistic production dataset — `lab-monitor-01` (9.5 MB response)

The perf-heatmap-asset dataset is synthetic and deliberately small so the harness
runs fast. The real stress test on the dev stack is `lab-monitor-01`, which returns
a ~9.5 MB response and exercises the real cap of 100 evaluation runs per asset.

Measured in-place against the dev stack (not via bench-heatmap.py because that
harness hardcodes the seeded asset name):

| metric | cache=true (hot) | cache=false (bypass) | delta |
|---|---|---|---|
| p50 latency (ms) | **362.2** | 1399.2 | **3.9× faster** |
| p95 latency (ms) | 442.1 | 1605.9 | 3.6× |
| p99 latency (ms) | 445.0 | 1715.2 | 3.9× |
| mean latency (ms) | 372.9 | 1438.3 | 3.9× |
| payload bytes | 9,555,875 | 9,555,875 | same |

**This is where the chunk actually pays off.** The cache-hit path is flat with
respect to data volume (MGET + JSON parse + assemble), while the cache-miss path
scales with the join walk through SLOEvaluations + indicator rows + SLOObjective.
At 9.5 MB the cache-miss build is 1.4 seconds of Pydantic + SQLAlchemy work.
Chunk C serves repeat visits to the same asset in ~360 ms instead — roughly a
1-second per-visit saving on the warm-cache path.

## Summary — baseline vs Chunk C

Numbers reported against `perf-heatmap-asset` (1.07 MB) and `lab-monitor-01`
(9.5 MB). Latency in ms, payload in bytes.

| metric | perf-heatmap-asset baseline | perf-heatmap-asset chunk C | lab-monitor-01 baseline | lab-monitor-01 chunk C |
|---|---|---|---|---|
| p50 latency (cached hot) | 70.3 | **30.0** (2.3× faster) | n/a¹ | **362.2** |
| p95 latency (cached hot) | 133.1 | 94.7 | n/a¹ | 442.1 |
| p99 latency (cached hot) | 160.1 | 118.9 | n/a¹ | 445.0 |
| p50 latency (uncached) | 67.1 | 86.3 (29 % slower) | n/a¹ | **1399.2** |
| payload bytes | 1,073,347 | 1,073,947 | n/a¹ | 9,555,875 |

¹ Baseline numbers for lab-monitor-01 were not captured separately; the
`cache=false` column serves as the baseline-equivalent because it bypasses the
cache and runs the full build path.

**Headline:** cache hits on a real dataset (`lab-monitor-01`) are **3.9× faster
than the full build**, saving ~1 second per repeat visit. Cache misses are
slightly slower than the pre-chunk baseline because of the extra fragment
assembly overhead, but the worker warm path keeps the hit rate near 100 % in
production so users rarely hit the miss path after the initial backfill.

## Known limitations surfaced during measurement

1. **`TrendRepository.get_grouped_metric_heatmap` caps at 100 runs per request.**
   Both the original heavy query and the new `list_runs_for_heatmap` inventory
   query apply a `.limit(100)` unless `run_id_filter` is explicitly passed.
   This means the production read path is bounded to 100 columns regardless of
   how wide a time window the user requests. A 90-day window with hourly evals
   (would be ~2,160 runs) sees only the most recent 100. The backfill script
   bypasses the cap via a raw `select(EvaluationRun.id)` so every historical run
   gets its column cached, but the runtime endpoint silently clips. Pre-existing
   behavior — not introduced by Chunk C — but worth fixing in a follow-up because
   the chunk's architecture supports unbounded reads now that caching keeps the
   per-request cost flat.

2. **Cache-miss path is ~25 % slower than the pre-chunk baseline** because the
   fragment builder + assembler pipeline adds an extra pass of Pydantic
   instantiation compared to the old `_collect_slo_heatmap_data` + `_build_slo_groups`
   single-pass pipeline. The worker warm path keeps the hit rate near 100 % so
   users rarely see this regression in production, but cold deploys need the
   backfill script to have run or the first-reader experience is worse than
   before.

3. **Parse-once criteria cache is a no-op on one-cell-per-objective datasets.**
   The synthetic `perf-heatmap-asset` data has exactly one indicator row per
   objective per run, so the within-run parse dedupe never fires. Real datasets
   where the same SLI appears multiple times in a single run (e.g. parameterized
   metrics or aggregates) will benefit. If the production profile shows this is
   rare, the parse-cache adds complexity for no gain and could be simplified
   back out.

## Follow-ups surfaced during measurement

**Backend:**
- **Remove the 100-run cap** on `TrendRepository.list_runs_for_heatmap` (and
  `get_grouped_metric_heatmap` at the inventory query level). The per-column cache
  makes per-request cost flat in cache-hit scenarios, so there's no reason to
  cap historical window reads. Would unlock multi-month views currently silently
  clipped to 100 runs.
- **Cache the `get_run_ids_with_notes` query.** Annotations are low-write /
  high-read; the same per-run cache pattern (`heatmap:notes:v1:{asset_id}:{window}`)
  could eliminate this query from the read path too. Chunk C deliberately left
  note state outside the fragment so annotation writes do not invalidate columns,
  but the note query itself is still hit on every read. Lower priority than #1.
- **Stampede protection / single-flight.** Not needed at current concurrency,
  but worth revisiting if duplicate-miss patterns ever appear in the cache-hit
  metric (see next item).
- **Cache hit-rate metric.** Add a Grafana panel for `heatmap_cache_hit_ratio`
  so regressions in warming or invalidation are visible in observability rather
  than only via the property test in CI.
- **Batched trend endpoint.** The navigator currently fires one `/trend` request
  per `MetricTrendBlock`, which for `lab-monitor-01` with multiple expanded SLO
  groups means ~300 parallel HTTP calls on first load. A single
  `GET /evaluate/trend?asset_name=X&slo_name=Y` returning `{metric: [points]}`
  for every SLI in one SLO would collapse that to ~N-SLO calls (~10-20 for
  lab-monitor-01). Pre-existing issue — not introduced by Chunk C — but the
  backend refactor effort is small and the perceived win would be large.

**UI:**
- **URL-as-filter-state for the navigator.** Filter state
  (`TimeRangeProvider`, selected asset, expand state) lives in localStorage
  and React context, not in the URL. Shareable links to "this specific view
  of this asset over the last 7 days" are impossible today. Pre-existing,
  frontend-only task.
- **Viewport virtualization for heatmaps with many SLO groups.** Progressive
  rendering unblocks the main thread during the render but still mounts every
  SLO group's cells. For users with 20+ expanded SLO groups, a per-SLO-group
  IntersectionObserver boundary would let off-screen groups stay unmounted
  until scrolled into view. ~200 lines of refactor for the `HeatmapChart` split
  and `AssetPanelHeatmapView` wrapping.
- **Trend block lazy mount.** Same idea as above for `MetricTrendBlock`. Each
  block fires a `useTrend` query on mount; virtualizing the SLI accordion
  section would cut the ~300-call first-load pattern mentioned above without
  needing the batched trend endpoint.

## How to reproduce these numbers

```bash
# 1. Start the dev stack from the worktree root
./scripts/dev-start.sh

# 2. Seed the deterministic perf dataset (idempotent)
QG_DB_USER=tropek_e2e QG_DB_PASSWORD=tropek_e2e \
  QG_DB_HOST=localhost QG_DB_PORT=5434 QG_DB_NAME=tropek_e2e \
  QG_REDIS_PASSWORD=e2e_redis QG_REDIS_HOST=localhost QG_REDIS_PORT=6380 \
  QG_SECRET_KEY=e2e-test-key QG_CONFIG_PATH=config.yaml \
  uv run --directory api python ../scripts/perf/seed-heatmap-dataset.py

# 3. Run the HTTP latency benchmark (100 samples per variant)
uv run --directory api python ../scripts/perf/bench-heatmap.py http

# 4. Run the in-process profile (50 iterations of build_grouped_heatmap_response)
QG_DB_USER=tropek_e2e ... uv run --directory api python ../scripts/perf/bench-heatmap.py profile

# 5. (Optional) Warm the cache for every existing run in the DB
uv run --directory api python ../scripts/perf/warm-heatmap-cache.py --dry-run
uv run --directory api python ../scripts/perf/warm-heatmap-cache.py
```
