# Evaluations

## Purpose

The Evaluations feature is the primary way users inspect, manage, and act on quality gate
results. It surfaces SLO evaluation outcomes across assets and time, with tools for
drilling into individual indicator scores, viewing metric trends, and performing corrective
actions like invalidation, override, re-evaluation, and baseline pinning.

## Key Concepts

| Term | Meaning |
|---|---|
| **Evaluation** | A single SLO evaluation run against an asset for a specific time period. Produces a score and an outcome (pass, warning, fail). |
| **Outcome** | The final status of an evaluation: **pass**, **warning**, **fail**, **error**, or **invalidated**. |
| **Indicator (SLI)** | An individual metric evaluated within an SLO. Each indicator has a measured value, a score, a weight, and pass/warning criteria. |
| **Score** | A weighted percentage (0--100) computed from individual indicator scores. Compared against pass/warning thresholds to determine outcome. |
| **Baseline** | A reference evaluation that subsequent evaluations are compared against for relative criteria (e.g., "no more than 10% slower"). |
| **Baseline pin** | Locks a specific evaluation as the baseline, preventing automatic baseline advancement. |
| **Key SLI** | An indicator flagged as critical -- its failure alone can cause the evaluation to fail regardless of overall score. |
| **Tab group** | A category label (Performance, Reliability, etc.) used to organize indicators into filterable groups. |
| **Annotation / Note** | A user-authored comment attached to an evaluation, with an optional category for colour-coded organization. |
| **SLO scope** | When performing batch actions, the set of SLOs the action applies to. Users can narrow scope via a multi-select picker. |

## Views and Interactions

### Evaluation List (Navigator)

The navigator page shows evaluations in two complementary views:

- **Heatmap** -- A grid of coloured cells where rows are assets and columns are time slots.
  Cell colour reflects the worst outcome in that slot (pass = green, warning = yellow,
  fail = red, invalidated = gray). Clicking a cell selects that time slot to filter the
  table below; clicking again on the same slot selects the asset.

- **Data table** -- A paginated table showing evaluations matching current filters. Fixed
  columns include evaluation name, asset, time period, score, result, SLO, and notes.
  Dynamic columns for asset tags and variables can be toggled via a column picker in the
  header. Clicking an evaluation name opens its detail page.

When the evaluation count exceeds the configured maximum, an amber truncation warning
appears above the table.

### Evaluation Detail Page

Accessed by clicking an evaluation in the list or navigating to its URL directly. The page
is organized into three sections:

#### Summary Card

A header card showing:

- **Left**: Evaluation name, result badge (coloured pill), asset info, tags, time period,
  SLO version, ingestion mode, and adapter used.
- **Center**: Numeric score with pass/warning threshold indicators.
- **Right**: Action menu button and note count badge.

Conditional badges appear when the evaluation has been:
- **Invalidated** -- red badge with invalidation reason.
- **Overridden** -- amber badge showing original vs. overridden result.
- **Baseline pinned** -- badge with pin author and timestamp.
- **Re-evaluated** -- badge indicating this evaluation was produced by re-evaluation.

#### SLI Breakdown Table

A table listing every indicator in the evaluation:

| Column | Description |
|---|---|
| Metric | Indicator name (key SLIs marked with a diamond icon) |
| Value | Measured value |
| Baseline | Compared baseline value (if available) |
| Delta | Absolute and relative change from baseline |
| Weight | Indicator weight in the overall score |
| Score | Points earned out of maximum |
| Status | Pass/warning/fail badge |
| Criteria | Pass and warning thresholds (violated criteria highlighted in red) |

Indicators can be filtered by tab group using the tab bar above the table (All,
Performance, Reliability, etc.). Each tab shows its indicator count.

For aggregated SLIs (metrics computed from multiple samples), the table shows sample
counts and a "low confidence" badge when more than 20% of data points are missing.

Clicking the trend icon next to an indicator scrolls down to its trend chart.

#### Metric Trend Charts

Below the SLI table, a responsive grid of charts shows each indicator's value over time:

- **Data points** are coloured by outcome (green/yellow/red dots).
- **Target lines** show pass and warning thresholds. A toggle dropdown controls which
  threshold lines are visible.
- **Annotations** appear as markers on the timeline when the notes toggle is enabled.
- **Y-axis controls** allow adjusting the visible range.
- **Click-to-navigate** -- clicking a data point opens the corresponding evaluation detail.

### Actions

The action menu in the summary card header provides five operations. Each opens a floating
form panel on the right side of the page.

#### Invalidate

Marks evaluations as invalidated, removing them from scoring and trend analysis. Requires
a reason and author. The SLO scope picker lets you narrow invalidation to specific SLOs
when multiple are in scope.

After submission, a result summary shows per-SLO success or failure with a "Retry failed"
button for any that did not succeed.

#### Override Result

Changes the evaluation outcome to a different value (pass, warning, or fail) without
re-running the evaluation. Requires a reason and author. Evaluations whose result already
matches the target are automatically skipped.

#### Pin as Baseline

Locks the evaluation as the baseline for future comparisons. A warning appears when
creating more than 5 simultaneous baseline pins. Requires a reason and author.

#### Re-evaluate

Re-runs the evaluation engine against the same data. Two modes are available:

- **From date** -- re-evaluate all evaluations from a specific date forward.
- **From baseline** -- re-evaluate starting from the current baseline.

If a baseline pin conflict is detected, the form offers two resolution options:
"Start from pin" (skip to the pinned evaluation) or "Ignore pin" (proceed past it).

The result summary shows old and new outcomes and scores for each affected evaluation.

#### Restore

Un-invalidates previously invalidated evaluations, returning them to their original
outcome. No reason or author required.

### Notes

The notes section at the bottom of the detail page supports:

- **Adding notes** via an inline form with content, author, and category picker. Categories
  have assigned colours that appear as accent bars on note cards.
- **Viewing notes** in compact (single-line) or expanded (full metadata) mode. Notes from
  re-evaluation operations are grouped together in a distinct amber-themed card.
- **Hiding notes** -- notes can be hidden (soft-deleted) with a reason. Hidden notes remain
  in the system but are no longer displayed.
- **URL auto-linking** -- URLs in note text are automatically converted to clickable links.

The note count badge in the header provides quick access; clicking it scrolls to the notes
section and opens the add-note form.

### Trigger Evaluation

A dialog accessible from the navigator allows manually triggering a new evaluation. The
form collects:

- **Asset** -- selected from available assets.
- **Evaluation name** -- a label for the run.
- **Time period** -- start and end timestamps.
- **Variables** -- key-value pairs passed to SLI queries.

## URL State

The evaluation detail page uses the evaluation ID from the URL path parameter
(`/evaluations/:id`). The navigator page manages filters (asset, evaluation name, date
range) through its own URL state mechanism.

## Related Features

- **Navigator** -- the primary entry point for browsing evaluations across assets and time.
  The heatmap and data table live here; evaluation actions depend on navigator data
  structures for SLO scope derivation.
- **SLO Registry** -- defines the SLO configurations that evaluations are run against.
  SLO names and versions appear throughout the evaluation UI.
- **SLI Registry** -- defines the metric queries that produce indicator values.
- **Assets** -- the services/projects being evaluated. Asset names, display names, and tags
  are shown in evaluation cards and used for filtering.
- **Note Categories** -- provides the category palette used for colour-coding annotations.
- **Datasources** -- adapter configurations used to query metric backends during evaluation.
