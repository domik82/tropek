# Navigator

## Purpose

The Navigator is the primary evaluation monitoring view in TROPEK. It provides a
time-series overview of quality gate evaluations across all assets (services,
projects, or environments) using stacked mini-heatmaps for at-a-glance status and
detailed drill-down panels for investigation. Users land here to answer "how is my
service doing?" and "what changed?"

## Key Concepts

| Term | Meaning |
|---|---|
| **Asset** | A monitored entity (service, project, environment) that has SLO evaluations. |
| **Asset group** | A logical grouping of assets for organizational purposes. |
| **Evaluation** | A single quality gate run that scores an asset against its SLO definitions. |
| **Evaluation name** | A label distinguishing evaluation types (e.g. "load-test", "prod-validation"). Multiple evaluation names can exist for the same asset. |
| **SLO** | Service Level Objective -- a named quality target containing one or more indicators. |
| **Indicator (SLI)** | An individual metric measured within an SLO (e.g. response time, error rate). |
| **Column** | A single evaluation run shown as a vertical slice in the heatmap. Columns are identified by evaluation ID, not timestamp, because two runs can share the same time. |
| **Result** | The outcome of an evaluation: **pass**, **warning**, **fail**, **error**, or **invalidated**. |
| **Composite score** | The overall weighted score across all SLOs in a single evaluation run. |

## Views & Interactions

The Navigator page has three panel modes, determined by what is selected in the
sidebar asset tree.

### All Evaluations Panel (default)

When no asset or group is selected, the Navigator shows a summary of all recent
evaluations across every asset.

- **Heatmap grid** -- rows are assets, columns are time slots. Cell color indicates
  pass/warning/fail status.
- **Evaluation table** -- tabular listing of recent evaluations with scores and
  results.
- **Evaluation name filter** -- chip-based filter to show only evaluations with a
  specific name (e.g. show only "nightly-regression" runs).
- Clicking an asset row or evaluation entry navigates to the asset detail panel.

### Group Panel

When a group is selected in the sidebar tree, the Navigator shows evaluations for
all assets in that group.

- **Group heatmap** -- same assets-by-time grid, filtered to the selected group.
- **Chart mode toggle** -- switch between heatmap view and a stacked bar chart
  showing group-level scores.
  - The bar chart supports an **absolute/normalised toggle** to compare assets with
    different score scales.
- **Evaluation table** -- same as the all-evaluations view, scoped to the group.
- Clicking an asset navigates to the asset detail panel while preserving the group
  context.

### Asset Panel (primary detail view)

When an asset is selected, the Navigator shows the full evaluation detail for that
asset. This is the most feature-rich panel and supports two view modes.

#### Heatmap Mode

The default view. Centered around the **stacked mini-heatmap** -- a vertically
stacked set of independent heatmap segments:

1. **Overall Score segment** -- a single-row heatmap showing the composite score
   for each evaluation run. Color indicates the overall result.
2. **Per-SLO segments** -- one segment per SLO definition. Each can be
   collapsed (single header row showing SLO-level score) or expanded (header row
   plus one row per indicator metric).
3. **Shared time axis** -- all segments share a common x-axis showing evaluation
   timestamps.
4. **Color legend** -- a single shared legend below all segments.

Interacting with the heatmap:

- **Click a cell** to select the entire evaluation column. The selected column is
  highlighted across all segments.
- **Click an SLO header row** to expand or collapse that SLO's indicator rows.
- **Click an indicator cell** in the already-selected column to scroll to that
  metric's row in the SLI breakdown table below.
- Expanded SLO segments with many rows are **lazy-loaded** -- they mount only when
  scrolled near the viewport, keeping the page responsive.

Below the heatmap, the selected evaluation's details are shown:

- **Evaluation header** -- evaluation name, timestamp, overall score, and result
  badge.
- **SLI breakdown table** -- grouped by SLO, showing each indicator's measured
  value, score, weight, pass/warning criteria, and result. Clicking an indicator
  name scrolls to its trend chart.
- **Per-SLO trend charts** -- time-series charts for each indicator, grouped under
  their SLO. Each chart header has a button to scroll back to the heatmap.
- **Annotation section** -- notes and annotations attached to the selected
  evaluation.
- **Action menu** -- available actions for the selected evaluation:
  - **Override** -- manually override an indicator's result.
  - **Invalidate** -- mark evaluation results as invalidated (e.g. due to a known
    infrastructure issue).
  - **Restore** -- undo an invalidation.
  - **Set baseline** -- mark this evaluation as the comparison baseline for future
    runs.
  - **Re-evaluate** -- trigger a fresh evaluation using the same parameters.

#### Chart Mode

An alternative view toggled via the view mode switch:

- **Score chart** -- a line chart showing the composite evaluation score over time.
  The selected evaluation is highlighted with a larger marker. Invalidated
  evaluations appear as diamond shapes.
- **Per-metric trend blocks** -- a flat grid of individual metric charts, filterable
  by metric group using a tab-group filter.
- Clicking any chart point selects the corresponding evaluation column.

### Sidebar Asset Tree

The left sidebar shows the asset tree hierarchy. It supports:

- Selecting a group to view the group panel.
- Selecting an asset to view the asset detail panel.
- Deselecting (clicking the selected group again) to return to the all-evaluations
  view.

### Evaluation Name Filter

Available in all three panels. Shows chip buttons for each evaluation name present
in the data:

- **All** -- show all evaluation names (default).
- **Individual chips** -- click to filter to a single evaluation name. Click
  additional chips to add them to the filter.
- The last active chip cannot be deselected -- at least one name must be shown.

### Time Range Picker

Controls the time window for displayed evaluations. Available in the asset panel
and group panel headers.

## URL State

The Navigator preserves selection state in URL search parameters for bookmarking
and sharing.

| Parameter | Effect |
|---|---|
| `?asset=<name>` | Opens the asset detail panel for the named asset. |
| `?group=<name>` | Opens the group panel. Ignored when `asset` is also present. |
| `?eval=<id>` | Pre-selects a specific evaluation in the asset panel. |

Priority: `asset` > `group` > all-evaluations (no params).

Navigating between panels replaces all URL parameters to keep the URL clean. The
`group` parameter is preserved when drilling from a group view into an asset, so
the back button returns to the group context.

## Related Features

- **Evaluations** (`features/evaluations/`) -- provides the evaluation detail
  components used within the asset panel: header, action forms, SLI breakdown
  table, metric trend charts, and the generic evaluation heatmap/table used in
  group and all-evaluations views.
- **Assets** (`features/assets/`) -- provides the asset tree data and asset
  metadata used for display names and grouping.
- **SLOs** (`features/slos/`) -- provides SLO definitions referenced by the
  evaluation detail view and action forms.
- **Registry** (`features/registry/`) -- the SLO registry where SLO definitions
  are created and managed, linked from evaluation contexts.
