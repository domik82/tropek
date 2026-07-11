# Trend batch endpoint + per-SLO fragment cache — design

**Date:** 2026-07-11
**Status:** approved design, pending implementation plan
**Scope:** Option 1 (trend layer) now; Option 2 (heatmap split) documented as a follow-up phase.

## Problem

Opening a 6-month asset view in the Navigator takes ~12–21 s. Evidence from
`load_6m_data.har` (win10-toolset, ~46 SLOs × 5–13 indicators):

- **499 requests fired in one burst**, max 484 concurrent.
- ~439 of them are per-indicator `GET .../slos/{slo}/trend?metric=…` calls.
- Server processing is fast: trend `wait` (TTFB) p50 108 ms, mean 212 ms; total
  server time across all requests only 103 s.
- The wall-clock cost is browser-side queueing: HAR `blocked` summed 5204 s
  (mean 10.7 s/request). The browser's ~6-connection HTTP/1.1 limit serializes
  the burst.

Root cause of the burst: the Navigator's SLO groups are **expanded by default**
(`heatmapSloGroupsExpandedByDefault: true`), so every `MetricTrendBlock` mounts
at once and each fires its own `useTrend` request. The UI is already decomposed
per SLO; it just mounts all groups eagerly.

Two facts frame the fix:

1. The trend endpoint (`get_trend_by_asset_slo`) has **no server cache** and no
   HTTP cache headers. Only the grouped heatmap uses a Redis fragment cache.
2. The grouped heatmap is a single `/evaluations/heatmap` fetch (~40 MB, ~8.9 s)
   that the UI slices client-side into per-SLO render groups. Its size is a
   separate problem, addressed in the Option 2 follow-up.

This is a request-fan-out problem, not a backend, Redis, or DB problem. Redis
alone cannot fix it — a server cache shaves the ~200 ms server time, not the
~10 s browser queue. The fix must reduce request count and defer requests until
needed.

## Non-goals

- HTTP/2. Browser HTTP/2 requires TLS; once the fan-out is removed, ~46 requests
  over HTTP/1.1 no longer bottleneck. Revisit when TLS is on the table for prod.
- Worker-count changes. The 2-worker limit is not the read bottleneck (server
  p50 was 108 ms); it affects imports/writes.
- Splitting the grouped heatmap endpoint — see Option 2 follow-up.

## Approach (Option 1)

Three coordinated changes.

### 1. Per-SLO batch trend endpoint

```
GET /assets/{asset_name}/slos/{slo_name:path}/trends?from=&to=
  → SloTrendsResponse = { metric_name: list[TrendPoint] }
```

Returns every indicator's series for one SLO in a single response. This takes
the ~439 per-indicator calls down to one call per SLO (~46), and — combined with
lazy loading below — those fire only as groups become visible.

The existing single-metric route (`.../slos/{slo}/trend?metric=`) stays: it is
still used by `/evaluation/{eval_id}/trend` and external callers. We add, not
replace.

`TrendPoint` is unchanged (`timestamp, value, score, eval_id, result, baseline,
evaluation_name, targets, change_point`).

### 2. Dedicated per-(run, SLO) trend fragment cache

A new cache, modeled on `HeatmapColumnCache` but grained per SLO-evaluation
rather than per run.

**Why not reuse the heatmap fragment.** The per-run `HeatmapColumnFragment`
bundles all SLOs. Serving one SLO's trend from it means MGET-ing and
deserializing the all-SLO blobs for every run in range; the heatmap's own
assembly of those fragments already costs ~2.2 s server-side (HAR). Doing that
per SLO (~46×) would be slower than the DB. Per-SLO access needs a per-SLO
grain.

**Fragment.** One fragment = one SLO's contribution to one run.

- Key: `trend:col:v{SCHEMA_VERSION}:{slo_evaluation_id}`
- TTL: 7-day backstop (matches heatmap cache).
- Contents: `slo_evaluation_id`, `run_id`, `slo_name`, `period_start`,
  `evaluation_name`, `schema_version`, and one entry per indicator:
  `metric, value, raw_score, weight, result, compared_value (baseline),
  pass_targets, warning_targets`.
- **Change-points are NOT stored.** They are overlaid at read time via
  `ChangePointRepository.get_change_points_for_range`, mirroring how the heatmap
  enriches change-points. This keeps a change-point recompute from needing cache
  invalidation.

**Read path** (`assemble_slo_trends`):

1. List `slo_evaluation_id`s for `(asset_id, slo_name, from, to)` via a
   lightweight inventory query, ordered `period_start` ASC.
2. `MGET` trend fragments for those ids.
3. Rebuild misses from the DB (one query loading the SLO's indicator rows for the
   missing runs) and `set_many` them back.
4. Project each fragment into `TrendPoint`s per metric:
   - `score = raw_score ÷ Σ(weight across this slo_eval's metrics) × 100`
     (self-contained within the fragment).
   - `baseline = compared_value`; `eval_id = slo_evaluation_id`;
     `targets` mapped from `pass_targets`/`warning_targets` →
     `TrendTargets{pass, warn}`.
5. Order points by `period_start` then `evaluation_name` (same tie-break as the
   heatmap so x-indices align across charts).
6. Overlay change-points; group by metric → `SloTrendsResponse`.

**Warming.** Lazy-populate: the first reader of an uncached SLO pays the rebuild
and writes the fragments; subsequent readers hit the cache. (Accepted:
"first person pays." Worker-side warm-on-completion, as the heatmap does, is a
possible later optimization but is out of scope to keep the worker hot path
untouched.)

**Invalidation.** On re-evaluation, delete the affected `slo_evaluation_id`s'
trend fragments at the same call site that deletes heatmap fragments
(`re_evaluation_service.py`, alongside `heatmap_cache.delete(...)`).

**Opportunistic.** A Redis failure never blocks: read misses fall through to the
DB build, write failures are logged and dropped. Identical policy to
`HeatmapColumnCache`.

### 3. Viewport-lazy per-SLO trend loading (UI)

Keep `heatmapSloGroupsExpandedByDefault: true` (current UX — groups visible), but
fetch a group's trends only when it scrolls into view:

- Replace per-indicator `useTrend(asset, slo, metric)` with one
  `useSloTrends(asset, slo)` per SLO group (`staleTime: Infinity`, as today).
- `MetricTrendBlock` selects its own metric's slice from the shared query
  (React Query `select`) so each block still re-renders only on its slice.
- Gate the fetch behind an `IntersectionObserver` on the SLO group (a small
  `enabled`-when-visible hook), so trend requests fire progressively as the user
  scrolls rather than all at once.

Net effect: no burst (requests spread across scroll), ~439 → one batched call per
visible SLO, and each call is a cache hit once warm.

## Cache contention

The earlier concern about heatmap and trends "fighting over the same data" is
resolved by the per-SLO grain plus lazy loading: trend fragments are separate
from heatmap fragments (no shared keys), and viewport-lazy loading means only the
SLOs the user actually scrolls to rebuild on a cold cache — naturally throttled,
no 46-at-once stampede. Trends own their own fragment writes; the heatmap owns
its. This supersedes the earlier idea of sequencing trends after the heatmap.

## Error handling

- Unknown asset / SLO → existing `NotFoundError`.
- A run where the SLO was not evaluated contributes no point (no error).
- Redis unavailable → DB build path, per the opportunistic policy above.

## Testing

- **Unit (pure):** `assemble_slo_trends` projection — score normalization,
  targets mapping, ordering/tie-break, empty-SLO runs, invalidated cells.
- **Parity property test:** for a given `(asset, SLO, range)`, the batch
  endpoint's points must equal the current single-metric endpoint's points,
  metric by metric — run with cache on and off (copy the heatmap suite's
  `cache=false` bypass). This is the safety net that the fragment projection
  matches the DB query.
- **Integration:** cold cache (rebuild + write) vs warm cache (MGET hit) return
  identical results; re-eval invalidation drops exactly the affected
  `slo_evaluation_id` fragments.
- **UI (vitest):** `useSloTrends` slice selection in `MetricTrendBlock`; the
  IntersectionObserver gate fires a group's fetch only when visible.

## Follow-up — Option 2 (deferred, not in this plan)

Split the grouped heatmap into per-SLO heatmap fetches that share the same
per-(run, SLO) grain, plus a small composite/summary endpoint for the Overall
row. This would fix the ~40 MB / ~8.9 s monolithic heatmap response and give one
uniform per-SLO progressive-load model across heatmap and trends. It is a larger
change — it touches the heatmap endpoint, the worker warm path, invalidation, and
`AssetPanel`'s composite/summary derivation — so it is intentionally deferred to
its own spec → plan cycle once Option 1 lands and is measured.
