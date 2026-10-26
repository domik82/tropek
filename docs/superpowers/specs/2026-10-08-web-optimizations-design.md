# Web optimizations: response compression + multi-process API — design

**Date:** 2026-10-08
**Status:** implemented on `feat/web-optimizations`, validated on a deployed instance
**Scope:** transport and process model only. No API contract change, no schema change.

## Goal

Make the Navigator's heatmap view load in roughly a second over a slow or high-latency link
(VPN), instead of ~10 s, without changing the API contract or requiring client changes.

## Problem

Opening the Navigator for an asset with ~60 evaluation columns took ~10–12 s, nearly all of it on
one request, `GET /evaluations/heatmap`. Browser timing split it into two separate costs.

### 1. Download: ~9 s — nothing in the stack compressed responses

- The grouped heatmap for such an asset is **~10 MB** of JSON: 62 columns, 28 SLO groups,
  ~14.4k cells, ~700 bytes per cell.
- The response carried no `Content-Encoding`. `ui/nginx.conf` had no `gzip` directives (and
  nginx defaults to off), and the API had no compression middleware.
- The body is extremely repetitive (the same keys, UUIDs and timestamps in every cell), so gzip
  shrinks it **15×**, to ~0.67 MB. At ~0.8 MB/s that is ~9 s versus well under a second.
- The main JS bundle (~2.5 MB, 3.3× compressible) was also served uncompressed.

### 2. "Waiting for server": ~2.4–2.7 s — one API process for every request

- The API image runs `uvicorn` with no `--workers`, so a single process and a single event
  loop serve everything.
- On its own, a cached heatmap request costs ~0.4–0.6 s of server CPU (parsing the cached column
  fragments, assembling, serialising).
- On page load the UI fires ~36 requests at once (heatmap, evaluation list, summary, ~20
  per-SLO trend-annotation calls, …). They all queue on that one core.
- Measured directly against the API, bypassing proxy and network: one heatmap alone took ~0.5 s,
  while **4 concurrent heatmaps took up to 2.2 s**, with the API process pinned at 100% of one
  core on a 4-core host.

## Design

### Compression in two places

| Where | What | Why there |
|---|---|---|
| API (`api/tropek/main.py`) | Starlette `GZipMiddleware(minimum_size=1024, compresslevel=5)` | Clients that call the API directly (tropek-client, CI pipelines) never go through the UI's nginx. |
| UI nginx (`ui/nginx.conf`) | `gzip on`, `gzip_proxied any`, level 5, `gzip_min_length 1024`, `gzip_vary on`, JSON/JS/CSS/text/SVG types | Static assets. For `/api/` the response already carries `Content-Encoding`, and nginx never compresses twice. |

- **Level 5, not Starlette's default 9.** Measured on the real 10 MB body: level 5 takes ~34 ms
  for 15.1×, while level 9 takes ~62 ms for 16.6×. The compression runs on the API event loop,
  so the cheaper level wins.
- **`gzip_proxied any` is required in nginx.** Without it, nginx skips compressing responses
  to requests that arrived through another proxy.
- **The client needs no change.** httpx sends `Accept-Encoding: gzip, deflate` by default and
  decodes transparently, and custom `headers=` merge into that default rather than replacing it.
  Guard tests pin both behaviours.

### Multiple API processes, sized against the DB connection budget

The shipped compose files set these on **the `api` service only**:

| Variable | Default | Effect |
|---|---|---|
| `TK_API_WORKERS` → `WEB_CONCURRENCY` | 4 | uvicorn worker processes |
| `TK_API_DB_POOL_SIZE` → `TK_DB_POOL_SIZE` | 5 | per-process pool |
| `TK_API_DB_MAX_OVERFLOW` → `TK_DB_MAX_OVERFLOW` | 5 | per-process overflow |

- **The DB pool is per process.** config.yaml's 10 + 20 × 4 api processes + the worker's 30
  comes to 150 connections, over PostgreSQL's default `max_connections=100` (97 usable).
  Exceeding it would refuse connections to anyone, including the evaluation worker mid-job.
  With the defaults above: 4 × 10 + 30 = **70**.
- **The worker keeps config.yaml's pool.** Its `max_jobs: 10` concurrent jobs need it. That is
  why these settings are compose env on `api`, not config.yaml changes.
- **The image default stays one process.** Turning on workers in the image would also need the
  smaller pool, and the worker shares that image. Running the image outside the shipped
  compose files keeps the old behaviour until both variables are set.

#### Why multiple processes are safe

Reviewed against the code before enabling:

- **No process-local mutable state.** All caches (baseline, SLO/SLI definitions, annotation
  counts, heatmap/trend column fragments) live in Redis. The only `lru_cache` is the read-only
  `get_settings()`.
- **No API-side background work.** The finalize sweeper and stuck-job watchdog are arq cron
  jobs in the worker, which already dedups them across replicas.
- **Read-your-writes holds across processes.** `SessionMiddleware` commits *before*
  `http.response.start`, so by the time a client sees a 2xx the write is visible to every
  process.
- **No shared connection pools.** uvicorn spawns its workers (not fork), so each process
  builds its own SQLAlchemy engine.
- **Worker-side lock contention is unchanged.** The TimescaleDB chunk-lock deadlock and the
  former per-row PATCH fan-out (now batch endpoints) are about the worker and bulk actions. API
  process count doesn't change worker concurrency. API writes already reached the DB
  concurrently from a single async process, and remain wrapped in the deadlock retry.
- **Nothing changes for the UI.** Each request is still served whole by one process, and
  responses already arrived out of order.

## Results (deployed instance, same asset, over VPN)

| | Before | After |
|---|---|---|
| Heatmap transfer | 10.08 MB | 0.67 MB |
| Heatmap total (curl, fresh connection) | ~8.7–11.9 s | ~2.7–4.7 s |
| 4 concurrent heatmaps, server only | 0.68–2.23 s | 0.40–0.92 s |
| 8 concurrent heatmaps, server only | — | 0.57–1.61 s |
| API memory | ~660 MiB | ~865 MiB |
| API idle DB connections | 6 | 8 |

What remains after compression is mostly link latency, not bandwidth: ~250 ms RTT, TCP slow
start on a fresh connection, and two round trips per request.

## Rejected

- **Paging the heatmap.** It moves the same bytes over more round trips, and on a
  high-latency link round trips are the cost.
- **Having the router serialise its own `Response(model_dump_json())` to skip FastAPI's
  response handling.** Benchmarked on the real body: FastAPI 0.141 already serialises through
  pydantic-core (27.9 ms versus 32.0 ms hand-rolled, byte-identical output). There is no second
  validation pass to remove.

## Follow-ups (measure first)

1. Add a `Server-Timing` header to the heatmap route, one span per stage (runs query, cache
   read, DB rebuild, notes, assembly, change points). The local CPU total (~125 ms) doesn't
   account for the ~0.4–0.5 s observed in deployment.
2. Depending on what dominates:
   - **Parsing:** assemble the response from cached JSON without parsing it. This needs
     `has_notes` / `change_point` moved out of the cells, which is a contract change.
   - **Payload size:** `response_model_exclude_none` (~13% of the body is null fields).
     Needs a null-versus-missing audit in UI and client.
   - **DB:** query plans, and overlapping independent queries.
3. Batch the per-SLO `trend-annotations` calls into one request. That roughly halves the
   page-load request count, and each request pays a full round trip.
