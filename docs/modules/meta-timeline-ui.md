# Meta-Timeline

## Purpose

The Meta-Timeline provides a visual history of changes and events that occurred alongside
your evaluations. It renders a Gantt-style timeline below the heatmap in the asset panel,
showing colour-coded spans that represent deployments, configuration changes, incidents,
or any other tracked events. This gives you the context needed to correlate evaluation
results with what was happening in your environment at the time.


## Key Concepts

**Timeline span** -- A horizontal bar on the timeline representing a single tracked event.
Each span has a start time, an end time (or remains open-ended), a content label, and a
source identifier. Spans are colour-coded automatically based on their content text.

**Group** -- Spans are organised into groups displayed as rows on the timeline. Group IDs
encode a hierarchical path (for example, environment > region > cluster), and tooltips
display the full path as a breadcrumb trail.

**Focus marker** -- A vertical line on the timeline labelled "This evaluation" that marks
the end time of the currently selected evaluation. It provides a visual anchor so you can
see what events were happening around the time of a specific evaluation.

**Note category** -- A user-defined tag that can be applied to annotations and notes.
Categories have a name, a short label, a colour from a fixed palette, and a visibility
toggle that controls whether annotated items appear on the graph.

**Span colour** -- Each span is assigned one of 8 colours deterministically based on its
content text. The same content always produces the same colour across sessions and users.
Colours are chosen to avoid the green/red/amber hues reserved for pass/warning/fail status.

**Category colour** -- Categories use a separate, user-selectable palette of 8 named
colours: sky, green, amber, red, purple, pink, slate, and gray. These appear on category
badges and chart annotations.


## Views & Interactions

### Timeline view (asset panel)

The timeline appears below the heatmap when viewing an asset. It has two states:

**Collapsed** -- Shows a compact strip with an item count summary (for example,
"12 items tracked -- click to investigate changes over time"). The item count is always
fetched, even when collapsed, so you can see at a glance whether there are events to
explore. Click the strip or the chevron icon to expand.

**Expanded** -- Renders the full interactive timeline using the vis-timeline library
(a specialised Gantt/timeline component, not ECharts). The timeline loads data lazily --
no network request is made until you expand it.

Once expanded, you can:

- **Pan** by clicking and dragging the timeline left or right to move through time.
- **Zoom** using the scroll wheel to narrow or widen the visible time window. The minimum
  zoom level is 1 hour; the maximum shows the entire time range.
- **Hover** over any span to see a tooltip with six lines of detail:
  1. Group path (displayed as a breadcrumb, for example "prod > us-east > cluster-1")
  2. Value (the span's content label)
  3. Start timestamp in UTC
  4. End timestamp in UTC, with an annotation if the span was clipped to the visible
     window, is still open, or was explicitly closed
  5. Duration (for example, "2 hours", "3 days")
  6. Source identifier

The timeline stays synchronised with the heatmap above it -- both share the same global
time range. When you adjust the time range picker, the timeline window updates to match.

### Category management page

Navigate to **Settings > Note Categories** (`/settings/note-categories`) to manage
categories. This page lets you:

- **View** all categories in a table showing name, label badge (with its assigned colour),
  visibility toggle, and action buttons.
- **Create** a new category by clicking "+ Add category". You must provide:
  - A name (lowercase letters, digits, and hyphens only, starting with a letter)
  - A label (1-12 characters, displayed on badges)
  - A colour chosen from the 8-colour palette via a visual picker
  - A "show on graph" toggle (enabled by default)
- **Edit** an existing category by clicking the pencil icon on its row. System categories
  (marked with a lock icon) cannot have their name changed.
- **Toggle visibility** directly from the table by clicking the "show on graph" checkbox.
  This controls whether items tagged with this category appear on evaluation charts.
- **Delete** a category by clicking the trash icon. A confirmation dialog appears. Any
  notes using the deleted category are automatically reassigned to the "info" category.


## URL State

The timeline does not maintain its own URL state. Its visible time window is controlled by
the global time range picker, which is shared with the heatmap and persisted in the URL.

The category management page is accessed at the route `/settings/note-categories`.


## Related Features

- **Heatmap / Navigator** -- The timeline renders directly below the heatmap in the asset
  panel and shares the same time range context.
- **Evaluations** -- The focus marker on the timeline corresponds to the currently selected
  evaluation's end time, providing temporal context.
- **Notes / Annotations** -- Note categories defined here are used to tag and colour-code
  annotations attached to evaluations.
- **Time range picker** -- The global time range controls what portion of the timeline is
  visible, keeping it synchronised with other time-aware views.
