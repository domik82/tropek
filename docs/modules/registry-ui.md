# Registry

## Purpose

The Registry is the central management interface for all quality gate definitions in TROPEK.
It provides a unified browser for creating, inspecting, and linking the core building blocks
of evaluations: SLO definitions, SLI definitions, datasources, asset groups, SLO templates,
and SLO groups. The three-panel layout lets users navigate a hierarchical tree of entities,
view details for any selected item, and perform CRUD operations without leaving the page.

## Key Concepts

- **SLO (Service Level Objective):** A versioned definition that specifies quality targets.
  Each SLO references an SLI and contains objectives with pass/warning criteria, weights,
  comparison settings, and score thresholds. SLOs come in two kinds: *standard* (concrete
  targets) and *template* (parameterized with generator variables for bulk SLO creation).

- **SLI (Service Level Indicator):** A versioned definition that describes what to measure.
  SLIs operate in two modes: *raw* (a list of named indicator queries) or *aggregated*
  (a query template expanded across multiple aggregation methods like avg, p95, max).

- **Datasource:** A connection to a metrics backend (e.g., Prometheus). Configured with an
  adapter type, URL, and optional authentication token. SLIs are linked to datasources
  through their adapter type.

- **Asset Group:** An organizational container for assets (services, environments, or any
  monitored entity). Groups form a hierarchy and receive SLO assignments that bind an SLO
  to a datasource for evaluation against that group's members.

- **SLO Template:** An SLO whose criteria use `$__gen_` variables as placeholders. Templates
  are not evaluated directly -- they are used by SLO groups to generate concrete SLOs.

- **SLO Group:** A generator that combines a template SLO with a set of variable values to
  produce multiple concrete SLOs. For example, a template with `$__gen_service` and values
  `api,web,worker` generates three SLOs with those values substituted.

- **Binding / Assignment:** The link between an SLO, a datasource, and an asset group. This
  triple tells the evaluation engine which SLO to evaluate, where to fetch metrics from,
  and which asset context to use for variable resolution.

- **Version:** Both SLOs and SLIs use append-only versioning. Every change creates a new
  version rather than editing in place. A `comparable_from_version` field controls which
  historical versions are eligible for baseline comparisons.

## Views & Interactions

### Three-Panel Layout

The Registry page is split into two main areas:

1. **Sidebar (left):** Contains a mode switcher, search/filter controls, the entity tree,
   and a create menu. Fixed-width panel.
2. **Detail panel (right):** Shows the detail view for whichever entity is selected in the
   tree. When creating or editing, this area is replaced by the appropriate form.

### Sidebar

**Mode switcher.** A segmented control at the top switches between three browsing modes:

- **Asset mode:** Shows the group hierarchy with nested assets and their SLO assignments.
  Each asset displays the full binding chain (SLO, SLI, datasource) as child nodes.
- **SLO mode:** Organizes definitions into three sections -- Standard SLOs, Templates, and
  Groups. Standard SLOs show their linked SLI and datasource as children.
- **Datasource mode:** Shows datasources at the top level with their associated SLIs and
  SLOs nested below.

**Search and tag filtering.** A text search filters tree nodes by name. A tag filter bar
lets users narrow results by key-value tags relevant to the current mode.

**Create menu.** A dropdown at the bottom of the sidebar offers creation actions for all
six entity types: SLO, SLO Template, SLO Group, SLI, Datasource, and Asset Group.

### Detail Views

Selecting any node in the tree opens its detail view in the right panel. Each detail view
has a colored accent strip at the top for visual entity identification.

**SLO detail.** Shows the SLO name, version badge, active status, objectives table (with
expandable query preview), comparison configuration, score thresholds, tags, variables,
notes, author, and linked asset groups. Actions: *New Version* (opens the SLO wizard
pre-filled), *Deactivate* (marks all versions inactive).

**SLI detail.** For raw SLIs, shows a table of indicator names and queries. For aggregated
SLIs, shows the query template, interval, and aggregation methods. Also displays cross-
references to SLOs that use this SLI. Actions: *New Version*, *Deactivate*.

**Datasource detail.** Shows the adapter URL, token status, and tags. Lists SLIs that use
this datasource's adapter type. Actions: *Edit* (opens the datasource form), *Delete*.

**Asset/Group binding view.** Shows the asset or group context with its variables and tags.
Lists all SLO assignments as cards, each displaying the binding chain breadcrumb
(SLO -> SLI -> Datasource), variable resolution, and the objectives table.
Actions: *Assign SLO*, *Edit*, *Unlink*.

**Template detail.** Similar to SLO detail but highlights `$__gen_` generator variables in
amber and lists referencing SLO groups with their generated SLO counts.

**SLO Group detail.** Shows the linked template SLO, generator variables table, and
generated SLO count. The *New Version* action opens an inline form where users can pick
a template version, edit variable values, and regenerate the group's SLOs.

### Creating an SLO (SLO Wizard)

The SLO wizard uses progressive disclosure across four steps. Later steps appear only
after earlier steps have meaningful data, reducing cognitive load.

**Step 1 -- Identity.** Enter the SLO name (lowercase, hyphens), display name, author,
and optional notes.

**Step 2 -- Pick SLI.** Select an SLI definition from a searchable dropdown. Tag-based
filtering narrows the SLI list. Once selected, the SLI's indicators are loaded for the
next step. In edit mode, the wizard auto-selects the matching SLI.

**Step 3 -- Indicators.** Configure criteria for each indicator. For raw SLIs, a table
shows each indicator with checkboxes to include/exclude, pass and warning criteria
(structured input with operator and value), weight, and key-SLI designation. Multiple
criteria per indicator are combined with AND logic. For aggregated SLIs, a method criteria
table shows per-method overrides with inherited vs. overridden values.

**Step 4 -- Comparison.** Configure baseline comparison settings (comparison count,
aggregate function, include-score toggle), score thresholds with a visual pass/warning/fail
bar, and optional tags and variables.

When creating a template SLO without `$__gen_` variables, the wizard shows a warning before
saving. The wizard is also used for creating new versions -- all fields are pre-filled from
the existing version.

### Creating an SLI

The SLI form opens as a modal dialog. Users choose between raw mode (add named indicators
with their queries) and aggregated mode (enter a query template, interval, and select
aggregation methods). The form includes name, adapter type, notes, author, and tags.

### Creating a Datasource

The datasource form opens as a modal dialog. Users enter a name, adapter type, adapter URL,
optional authentication token, and tags. In edit mode, the name and adapter type are
read-only.

### Creating an SLO Group

The SLO group form appears inline in the detail panel. Users enter a name, select a
template SLO, and define generator variables as key-value pairs (one key per line, with
comma-separated values). The group generates concrete SLOs by substituting each variable
combination into the template.

### Assigning SLOs to Groups

The SLO link dialog lets users bind an SLO to an asset group through a datasource. Three
searchable dropdowns select the SLO, datasource, and target group. The dialog detects
duplicate assignments and prevents them.

## URL State

The Registry persists its navigation state in URL search parameters, making selections
bookmarkable and shareable:

| Parameter    | Values                              | Purpose                            |
|--------------|-------------------------------------|------------------------------------|
| `mode`       | `asset`, `slo`, `datasource`        | Active browsing mode               |
| `selected`   | Entity name string                  | Currently selected tree node       |
| `type`       | `slo`, `sli`, `datasource`, `group`, `asset`, `binding`, `template`, `slo-group` | Node type of selection |
| `group`      | Group name string                   | Parent group context for selection |

Switching modes clears the current selection. Navigating between entities (e.g., clicking
an SLO's linked SLI) automatically switches the mode to match the target entity type.

## Related Features

- **Navigator** (`features/navigator/`): Consumes SLO assignments to display evaluation
  heatmaps per asset group. The navigator is the primary consumer of the bindings
  configured in the Registry.

- **Evaluations** (`features/evaluations/`): Shows evaluation results produced by running
  the SLOs defined in the Registry against live metrics.

- **Assets** (`features/assets/`): Provides the group hierarchy and asset definitions
  that the Registry's asset mode browses and that receive SLO assignments.

- **Datasources** (`features/datasources/`): Provides datasource CRUD and the adapter
  type registry that SLIs and assignments reference.

- **SLO Groups** (`features/slo-groups/`): Backend for template-based SLO generation,
  surfaced through the Registry's SLO group detail and creation forms.
