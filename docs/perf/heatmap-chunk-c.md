# Heatmap Chunk C — perf log

All measurements use `scripts/perf/bench-heatmap.py` against the dataset seeded
by `scripts/perf/seed-heatmap-dataset.py` (1 asset, 3 SLOs, 18 objectives,
200 runs, ~30 days).

Reproduce:

    just up
    uv run python scripts/perf/seed-heatmap-dataset.py
    uv run python scripts/perf/bench-heatmap.py http
    uv run python scripts/perf/bench-heatmap.py profile

## Baseline (commit `<sha>`, PR1)

_No caching exists yet; cache=true and cache=false fall through the same build path._

<paste http output>

<paste profile output>

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
