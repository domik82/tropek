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

## After PR2 — per-column Redis cache (commit `<sha>`)

<paste http output>

<paste profile output>

## Summary — baseline vs Chunk C

| metric | baseline | chunk C | delta |
|---|---|---|---|
| p50 (cached hot) | … | … | … |
| p95 (cached hot) | … | … | … |
| p99 (cached hot) | … | … | … |
| p50 (uncached) | … | … | … |
| payload bytes | … | … | … |

## Follow-ups surfaced during measurement

_Nothing yet._
