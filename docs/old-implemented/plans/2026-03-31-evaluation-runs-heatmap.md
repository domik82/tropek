# Evaluation Runs & Composite Heatmap Redesign — Index

This feature was split into two independent plans due to scope. Each plan produces working, testable software on its own.

## Plans

### [Plan A: DB Migration + Trigger Layer](2026-03-31-evaluation-runs-heatmap-a-db-trigger.md)

**Prerequisite:** `docs/superpowers/plans/2026-03-31-binding-model-hard-cut.md`

Covers phases 1–2 from the spec:
- Hard-cut Alembic migration: rename `evaluations` → `slo_evaluations`, create parent `evaluations` table, drop `evaluation_batches`, rename FK columns
- ORM model renames: `Evaluation` → `SLOEvaluation`, new `EvaluationRun`
- New trigger API: `POST /evaluate` and `POST /evaluate/batch` (by_date + by_asset)
- Worker rollup: parent `EvaluationRun` aggregates worst-case result + summed points when all children complete

### [Plan B: Grouped Heatmap API + Frontend](2026-03-31-evaluation-runs-heatmap-b-heatmap-frontend.md)

**Prerequisite:** Plan A above

Covers phases 3–8 from the spec:
- New endpoint `GET /evaluate/metric-heatmap` returning `GroupedMetricHeatmapResponse`
- Frontend types updated: `EvaluationColumn`, `HeatmapSloGroup`, new `MetricHeatmapResponse`
- `buildAssetHeatmapData` rewritten for grouped response + SLO expand state
- Heatmap accordion UI: `Map<slo_name, boolean>` expand state, SLO header rows, Overall row
- `SLIBreakdownGrouped` replaces `EvaluationTabs` + `SLIBreakdownTable`
- Trend charts: SLO-grouped collapsible sections
- Config flag `heatmap_slo_groups_expanded_by_default` wired end-to-end

## Spec

`docs/superpowers/specs/2026-03-31-evaluation-runs-heatmap-redesign.md`
