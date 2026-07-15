# Changelog

All notable changes to TROPEK are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.3-alpha] - 2026-07-15

### Added

- **Batched per-SLO trends with viewport-lazy loading** — `GET /assets/{asset_name}/slos/{slo_name}/trends` returns every metric's trend series for an SLO in one Redis-cached call, replacing the previous per-indicator fetch pattern that fired all ~439 trend queries at once on page mount. The UI's `useSloTrends` hook lazy-loads each SLO group only once it's expanded and enters the viewport (via the new `useInViewport` hook) (#73)

### Fixed

- **Batched trend queries computed each SLO-evaluation's objective weight via a per-row correlated subquery** — replaced with a single `GROUP BY` aggregate; a cold heavy-SLO `/trends` call on real-scale data (win10-toolset: 415 runs × ~7 indicators per SLO) dropped from 3-9s to ~0.12s server-side (#73)
- **Batched-trend cache wasn't invalidated on mutation** — the batched-trend query key root (`slo-trends`) was disjoint from `allTrends` (`trend`), so the 6 mutation success handlers that invalidate `allTrends` (override, invalidate, restore, pin, re-evaluate) left the batched cache stale with `staleTime: Infinity`. Added `evaluationKeys.allSloTrends`, invalidated alongside `allTrends` at every site (#73)

### Changed

- **Heatmap repository split out of `TrendRepository`** — the 5 heatmap methods and a shared `_apply_window_filters()` helper now live in `repositories/heatmap.py`; `trend.py` holds only trend queries. `RedisCache.client` property replaces direct `._redis` access at 3 call sites. Cryptic locals renamed repo-wide (`ev`→`evaluation`, `ir`→`indicator_result`, `obj`→`objective`, `exc`→`error`); dead `indicator_names` parameter removed from `_resolve_baselines` (#73)

## [0.1.2-alpha] - 2026-07-09

### Added

- **Chart view controls** — a columns toggle switches trend charts between 1 and 2 per row (wider charts spread note pills legibly instead of cramming them into clipped rows), a master notes switch shows/hides note pills across every chart at once while preserving per-chart override, a chart-type toggle swaps the metric series between line and bar, and hovering a datapoint now appends its notes to the tooltip. Preferences persist across sessions (#60)
- **URL-persisted, shareable time range** — the selected range is written to the URL as Grafana-style `from`/`to` search params, so a copied link reproduces the sharer's exact view. Presets stay relative (`?from=now-30d`, re-resolved per viewer); absolute ranges are pinned. The parser is tolerant — date-only (`?from=2026-04-01`) works, garbage input falls back safely. Previously a copied link carried only `?group=…&asset=…` and a colleague saw their own range (#66)
- **Bulk evaluation actions** — batch `PATCH` endpoints for invalidate, restore, override-status, restore-override, pin, and unpin, each returning `{results, updated, not_found}` so unknown or skipped ids don't fail the whole batch. Python client batch methods and UI forms use them instead of fanning out one request per row (#59)
- **`change_points` resource on the Python client** — `list`, `get`, `triage`, `bulk_triage`, `get_config`, `set_config`, `delete_config`. Previously the client exposed only `triage`, misplaced on `evaluations`, and could not list change points at all. `client.evaluations.triage` is retained as a delegating alias (#67)
- **Deadlock retry helper** (`tropek/db/retry.py`) — wraps the router unit of work, rolling back and re-running on Postgres `40P01` with jittered, bounded backoff; tunable via `config.yaml` under `quality_gate.invalidate.*` (#59)
- **FK index guard test** (`api/tests/db/test_indexes.py`) — asserts the indexes the hot read paths depend on are declared on the models (#70)
- **Local UI type checking** — `just typecheck-ui` (wired into `just check`) and a `tsc` pre-commit hook run CI's exact `tsc --noEmit` command. Previously the UI compile check ran only in CI, so a type error eslint cannot catch could be pushed cleanly and fail late (#63)

### Fixed

- **Change point magnitude is now the local adjacent-segment shift, not the diluted full-series split** — the change-point percentage shown in tooltips (SLI breakdown badge, mini heatmap), the Change Points page, and the asset panel was computed from a full-series split, which diluted the value, made it unstable as more history accumulated, sometimes reported the wrong direction, and always showed `0.00%` for appear/vanish transitions; it now reports the same local pre/post segment shift that the `min_magnitude` gate itself uses (Otava/Nyrkiö behavior). The Δ% column in the SLI breakdown table (value vs. baseline) was unaffected — it's a different field and was always correct (#64)
- **Same-regime dedup could suppress real change points** — the dedup check previously compared the same diluted full-series values described above, so it could treat two genuinely different regimes as "the same" and drop a real change point; it now compares the corrected local segment values
- **`change_relative_pct` is now null for appear/vanish transitions** — a new `transition` field (`appeared` / `vanished`) replaces the previous `0.00%` placeholder for changes from/to a zero segment mean
- **Mass invalidate/restore deadlocked the database** — a mass action (e.g. 144 indicators) fired one `PATCH` per SLO concurrently, each rewriting the whole column via `UPDATE ... WHERE evaluation_id`. Concurrent identical updates acquired row locks in diverging order and Postgres aborted a transaction (`40P01`), and the problem worsened as the database grew. Invalidate and restore now match `WHERE id` (#59)
- **Per-SLO invalidate/restore checkboxes were a no-op** — a latent whole-column bug exposed by the same `WHERE evaluation_id` predicate; selecting individual SLOs now affects only those rows (#59)
- **`GET /change-points` silently ignored the `metric_name` filter** — the endpoint declared its metric filter as `metric`, while every response field and sibling filter (`slo_name`, `asset_id`) uses the full name. A caller filtering by `?metric_name=…` — the name the returned objects expose — hit FastAPI's silent drop of unknown query params and got unfiltered results back (#67)
- **Heatmap reads sequentially scanned `slo_evaluations`** — no index led with `evaluation_id`, so every cold grouped-heatmap read scanned the whole table, with cost scaling to total table size rather than the requested window. On a seeded 120k-row dataset the query drops from 9.17 ms (seq scan) to 0.69 ms (bitmap index scan). This also fixes two hot note-path queries on the same unindexed column: `get_run_ids_with_notes()`, which runs on every heatmap render, and the `column-annotations` endpoint (#69, #70)
- **`column-annotations` over-fetched indicator rows** — `SLOEvaluation.indicator_rows` is `lazy='selectin'`, so the endpoint pulled every child's indicator rows despite never reading them; one fewer `SELECT` per request, payload unchanged (#70)
- **Hidden notes were filtered inconsistently** — `list_for_run` excluded them in SQL while `get_by_run_id` loaded every annotation and dropped hidden ones in the router. The predicate now lives in the relationship load, so both agree (#70)
- **Stuck-job watchdog retry counter was overwritten** — `mark_running` now merges `job_stats` (JSONB `||`) instead of replacing it, so `stuck_job_retries` survives the requeue → rerun cycle and the retry cap actually bounds a hard-crashing job (#59)
- **Non-body-parse `HTTPException`s lost their shape** — the custom exception handler now delegates them to FastAPI's default handler, preserving empty-body statuses, dict details, and headers (#59)

### Changed

- **Breaking (API): `GET /change-points` query parameter `metric` renamed to `metric_name`** — callers passing `?metric=…` now receive unfiltered results instead of filtered ones. Update to `?metric_name=…`, which matches the field name on every returned object (#67)
- **An invalidated SLO now marks the whole column invalidated** — the presenter's overall-invalidated derivation changed from `all()` to `any()`. This is a label change only; the score is unchanged (#59)
- **Change point migrations are now incremental** — migration `005` adds the `transition` column and makes `change_relative_pct` nullable; migration `006` reconciles pre-existing drift between `models.py` and migration history (`sli_values` eval-time index, `slo_groups` template FK) unrelated to this fix but discovered alongside it; migration `007` adds the `slo_evaluations.evaluation_id` index. Previously stored change points keep their old (pre-fix) values; only new detections use the corrected computation (#70)
- **Navigator change-point marker mapping moved into `mappers.ts`** — three inline DTO→domain conversions collapsed into one exported `changePointToMarker`, restoring the UI layering contract. Pure restructuring, no behavior change (#68)

### Security

- **OSV findings reduced from 16 vulnerabilities across 2 ecosystems to 5 across 1** — all PyPI advisories cleared via `starlette` 1.1.0 → 1.3.1, `pyjwt` 2.12.0 → 2.13.0, `pydantic-settings` 2.13.1 → 2.14.2, and `cryptography` 48.0.0 → 48.0.1 (#48, #50, #51, #52, #53)
- **npm transitive advisories cleared** — `@babel/core` 7.29.0 → 7.29.7 and `js-yaml` 4.1.1 → 4.2.0 (via `@redocly/openapi-core` 1.34.17), both resolved by a lockfile refresh; neither dev dependency needed a version bump (#71)
- **Known remaining:** 5 advisories against `hono` 4.12.23, including one High (7.1), reachable only through `shadcn` → `@modelcontextprotocol/sdk`. No upstream fix exists yet — the newest published MCP SDK still pulls the affected `hono`. `Dependency Audit` stays red until it bumps

### Dependencies

- `@tanstack/react-query` 5.100.11 → 5.101.2 (#44), the React group across 9 updates (#57), `vite` 8.0.14 → 8.1.3 (#49, #62), `shadcn` 4.8.0 → 4.10.0 (#47), the eslint group across 3 updates (#55), GitHub Actions across 3 updates (#54), grouped adapter and API updates (#56), and the observability stack's test generator (#42)

## [0.1.1-alpha.1] - 2026-07-01

Packaging re-release of `0.1.1-alpha` (published to PyPI as `0.1.1a1`), with a security patch and documentation.

### Added

- **`tropek-client` published to PyPI** — GitHub Actions workflow publishing on `v*` tags via Trusted Publishing (OIDC, no token); the version is derived from the tag per PEP 440
- **UI documentation** — annotated screenshots of the heatmap, asset view, trends, graphs, change points, SLO/SLI registries, data adapters, and evaluation actions

### Changed

- **`tropek-client` requires Python `>=3.12`** — deliberately wider than the monorepo's 3.13 target, so the client can be installed into older test environments

### Security

- **Pinned `size-sensor` against a malicious release** — versions 1.0.4, 1.1.4, and 1.2.4 were malicious, part of the Mini Shai-Hulud supply chain attack (2026-05-19). The installed 1.0.3 is clean and is now pinned via `pnpm-workspace.yaml` overrides to prevent an accidental upgrade, pending an `echarts-for-react` release that drops the dependency (MAL-2026-4153)
- **Patched 4 further vulnerabilities surfaced by the OSV scan** — `starlette` 0.52.1 → 1.1.0 (PYSEC-2026-161), `fast-uri` 3.1.1 → 3.1.2 (GHSA-v39h-62p7-jpjc, 7.5), `qs` 6.15.0 → 6.15.2 (GHSA-q8mj-m7cp-5q26, 6.3), and `ws` 8.20.0 → 8.21.0 (GHSA-58qx-3vcg-4xpx, 4.4)
- **Dependabot patches** — `urllib3` 2.6.3 → 2.7.0 (#37), `brace-expansion` 2.1.0 → 5.0.6 (#38), `idna` 3.11 → 3.15 (#39), and grouped uv updates (#40)

## [0.1.1-alpha] - 2026-05-08

### Fixed

- **Change point SLO key scoping** — change points are now keyed by `(slo_name, metric_name, period_start, period_end, evaluation_name)` instead of just `(metric_name, period_start)`, fixing incorrect CP marker collapse across SLOs sharing the same metric (#15)
- **Change point `period_end` mismatch** — CPs now store the `period_end` from the historical evaluation where the shift occurred, not the detecting evaluation
- **Change point `evaluation_run_id` semantics** — `evaluation_run_id` now points to the evaluation where the metric shift occurred; new `found_by_evaluation_id` column tracks which evaluation ran the detection
- **Heatmap y-axis label alignment** — SLO mini-charts now align y-axis labels across charts
- **Dependency vulnerabilities** — patched 21 dependency vulnerabilities, added OSV scanner to CI

### Added

- **Meta snapshot CRUD** — list, get, and delete endpoints for asset meta snapshots, with Python client methods and manifest support (`MetaSnapshot` kind)
- **Change points list page improvements** — asset name column, pagination (50/page), and default filter restored to "unprocessed"
- **Per-process mock data** — Office Apps scenario now generates distinct metric series per process (Word, Excel, Outlook, PowerPoint) with different change point positions
- **Dependency audit CI** — Dependabot configuration and OSV scanner workflow for automated vulnerability detection
- **Smoke test for CP scoping** — end-to-end test asserting CP markers differ across SLOs sharing a metric

### Changed

- **pnpm 10 → 11** — upgraded package manager; overrides moved from `package.json` to `pnpm-workspace.yaml` per pnpm 11 migration
- **`@types/node` 24 → 25** — TypeScript type definitions for Node.js
- **`path` renamed to `label_path`** — across meta snapshot schemas, pipeline, models, and tests (migration 003)
- **Data generators moved** — `tests/change_points/generators.py` relocated to `tests/helpers/data_generators.py` with added phase-based generation API compatible with mock adapter YAML scenarios
- **Zero npm audit vulnerabilities** — added `fast-uri` and `ip-address` overrides to patch remaining high/moderate findings

## [0.1.0-alpha] - 2026-05-01

Initial alpha release. TROPEK is a standalone quality gate and performance test
evaluation platform — a Python rewrite of Keptn's lighthouse-service, deployable
via Docker Compose without Kubernetes.

### Core

- **Evaluation engine** — pure-function SLO evaluation ported from Keptn's Go lighthouse-service (zero I/O, fully unit-tested)
  - SLO YAML parsing with embedded SLI queries (superset of Keptn 1.0 format)
  - Fixed threshold (`<600`), relative percent (`<=+10%`), and relative absolute (`<=+50`) criteria
  - Key SLI veto — one critical metric failure fails the entire evaluation regardless of score
  - Configurable baseline comparison (single result, several results with aggregate)
  - Per-objective scoring with pass/warning/fail and weighted total score calculation
- **Async evaluation pipeline** — FastAPI + arq (Redis) job queue with configurable concurrency (max_jobs=10)
  - Adapter-based data ingestion — pull metrics from Prometheus (shipped); custom adapters for other sources can be added
  - Multi-phase worker pipeline: fetch SLIs, evaluate, detect change points, store results
  - Evaluation batches — trigger evaluations for multiple assets in a single request
- **Change point detection** — E-Divisive algorithm (vendored from Apache Otava)
  - Per-metric configurable parameters (window size, p-value, min magnitude)
  - Automatic regression/improvement classification

### Registries & Data Model

- **SLO registry** — versioned SLO definitions with CRUD, validation, and dry-run test endpoint
- **SLI registry** — reusable SLI definitions with tagging
- **Asset & group registry** — hierarchical project/service grouping with metadata timeline and tags
- **SLO groups & templates** — organise SLOs into reusable groups, assign them to assets
- **Display groups** — control how SLI objectives are grouped and ordered in the UI
- **Data source registry** — register adapter instances (Prometheus, mock adapter for testing)
- **Comparison scoping** — `scope_tags` in SLO comparison config to scope baseline history per series

### Evaluation Actions

- **Annotations with categories** — attach categorised contextual notes to evaluations
- **Invalidation & restore** — mark evaluations as invalid and restore them without deleting data
- **Baseline pinning** — pin a specific evaluation as the comparison baseline
- **Status overrides** — manually override an evaluation's pass/warning/fail status
- **Re-evaluation** — re-run an evaluation against updated SLO criteria

### Adapters

- **Prometheus adapter** — standalone query adapter with SLI template variable substitution
- **Mock adapter** — data generator for testing and development

### Frontend

- **Navigator UI** — React 19 SPA with heatmap visualization of evaluation results across assets and time
- **Evaluation detail** — SLI breakdown table, trend charts, and evaluation actions
- **SLO management** — three-mode registry (tree, detail panel, sidebar)
- **Three-theme system** — dark (Radix-based), alt (neutral), light
- **Mock system** — MSW-based deterministic mocks for offline development (30 days history, 40 assets, 30 metrics)

### Infrastructure

- **Docker Compose deployment** — single-command setup with TimescaleDB, Redis, API, worker, UI, and adapters
- **Standalone deploy** — pre-built images on ghcr.io, download compose file from GitHub Releases
- **CI/CD pipeline** — GitHub Actions for lint, typecheck, unit tests, contract freshness, Schemathesis conformance tests
- **Docker security scanning** — Hadolint (Dockerfile lint) + Trivy (CVE scanning) in CI
- **Contract testing** — OpenAPI schema codegen + Schemathesis property-based API conformance tests
- **Python client** — typed client with CLI (not yet on PyPI)

### Tech Stack

- Python 3.13, FastAPI, SQLAlchemy 2 (async), PostgreSQL 16 + TimescaleDB, Redis 7, arq, uv
- React 19, TypeScript 5.9, Vite 8, Tailwind CSS 4, shadcn/ui, Apache ECharts 6, TanStack React Query 5, pnpm
