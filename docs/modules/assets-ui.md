# Assets & Datasources

## Purpose

Assets represent the things you monitor and evaluate in TROPEK -- typically projects, services,
or environments. You organize assets into groups to define evaluation scopes, and connect
datasources to tell TROPEK where to fetch metrics from. Together, assets, groups, and datasources
form the foundation that SLO definitions and evaluations build on.


## Key Concepts

**Asset** -- A named entity representing something you want to evaluate (a service, application,
environment, or any logical unit). Each asset has a type, optional display name, and key-value
labels for tagging and filtering.

**Asset Type** -- A classification for assets (e.g., "service", "environment", "application").
One type is marked as the default and is pre-selected when creating new assets. Types with no
assets assigned can be renamed or deleted.

**Asset Group** -- A named collection of assets and/or other groups, forming a hierarchy. Groups
define the scope for SLO evaluations -- when an SLO is linked to a group, evaluations run against
all assets in that group. Groups can be nested: a group may contain both direct asset members and
subgroups.

**Asset Group Tree** -- The hierarchical view of all groups. Top-level groups (those without a
parent) appear at the root. Subgroups are nested beneath their parent. The tree is navigable in
the sidebar and is used throughout TROPEK for group selection.

**Labels** -- Key-value pairs attached to assets. Labels are used for filtering and organization
in the sidebar and registry views.

**Weight** -- When an asset is a member of a group, it carries a weight value. Weights influence
how individual asset scores contribute to the group-level evaluation score.

**Datasource** -- A connection to a monitoring backend (e.g., Prometheus). Each datasource
specifies an adapter type, an adapter URL, and optional authentication. Datasources are referenced
by SLO definitions to determine where metric queries are sent during evaluation.


## Views & Interactions

### Assets Page

The Assets page is a two-panel layout accessible from the main navigation. The left panel shows
the asset group tree in a sidebar; the right panel shows either a group detail view or a flat
list of all assets.

#### Sidebar Tree

The sidebar displays all asset groups as an expandable tree. Clicking a group selects it and
shows its detail panel on the right. The tree supports:

- **Filtering** -- A text filter at the top narrows the visible groups by name.
- **Context menu** -- Right-clicking a group opens a menu with options to edit, delete, create
  a subgroup, link an SLO, or add an asset.
- **Inline rename** -- Groups can be renamed directly in the tree.
- **"All Assets" view** -- Selecting the ungrouped/root entry shows a flat table of every asset
  in the system.

An "Add Asset" button at the bottom of the sidebar opens the asset creation dialog.

#### Group Detail Panel

When a group is selected, the right panel shows:

- **Header** -- Group name, description, member count, and action buttons (Edit, Link SLO,
  Delete).
- **Subgroups** -- Clickable cards for each child group. Clicking navigates into that subgroup.
- **Members table** -- Lists all direct asset members with their type, labels, weight, and
  actions. Members can be removed from the group or have their labels edited inline.
- **Linked SLOs table** -- Shows all SLO definitions linked to this group, with an option to
  unlink each one.

#### All Assets Panel

When no group is selected (or the "All Assets" entry is chosen), the right panel displays a flat
table of every asset. Each row shows the asset name, type, labels, and a delete action with
inline confirmation.

### Creating an Asset

1. Click the "Add Asset" button in the sidebar footer.
2. Enter a name (must follow entity naming rules -- lowercase, no spaces, alphanumeric with
   hyphens/underscores).
3. Select an asset type from the dropdown (defaults to the system default type).
4. Optionally add labels as key-value pairs.
5. Optionally assign the asset to a group using the group tree picker, and set a weight.
6. Confirm to create the asset. If a group was selected, the asset is automatically added as
   a member.

### Creating a Group

1. Open the group creation dialog (via the sidebar context menu or the group detail panel).
2. Enter a name (same naming rules as assets).
3. Optionally set a display name and description.
4. Optionally select a parent group using the tree picker to nest this group.
5. Confirm to create. If a parent was selected, the new group is added as a subgroup.

### Editing a Group

The group edit dialog allows you to:

- Change the display name and description.
- Reassign the group to a different parent (or make it top-level).
- View and unlink SLO definitions that are currently linked to the group.

### Deleting a Group

Group deletion is a two-step process:

1. Choose how to handle linked SLOs: either keep them active (they remain but are unlinked from
   the group) or deactivate them.
2. Confirm the deletion in a second dialog.

Deleting a group does not delete its member assets -- they remain in the system and can be added
to other groups.

### Adding Assets to a Group

1. From the group detail panel, use the "Add Asset" action.
2. A searchable picker shows all assets not already in the group.
3. Click an asset to add it immediately as a member.

### Managing Asset Types

The asset types dialog (accessible from the Assets page) provides a table of all types with:

- **Inline rename** -- Click a type name to edit it; press Enter to save or Escape to cancel.
- **Set default** -- Mark a type as the default for new asset creation.
- **Delete** -- Remove a type (only available for types with zero assets assigned and that are
  not the default).
- **Add new** -- An inline form at the bottom of the table to create a new type.

### Datasources

Datasources are managed through the SLO Registry page rather than the Assets page. The registry
sidebar lists all configured datasources and provides filtering by datasource tags.

#### Creating a Datasource

When creating or editing a datasource, you specify:

- **Name** -- A unique identifier for the datasource.
- **Display name** -- An optional human-friendly label.
- **Adapter type** -- The type of monitoring backend (e.g., "prometheus").
- **Adapter URL** -- The endpoint where the adapter service is running.
- **Tags** -- Key-value pairs for organization and filtering.
- **Token** -- Optional authentication token for the adapter.

#### Using Datasources

Datasources are referenced when linking SLOs to assets. During evaluation, TROPEK uses the
datasource configuration to route metric queries to the correct monitoring backend through the
appropriate adapter.


## URL State

The Assets page persists selection state in URL search parameters:

| Parameter | Purpose                                    | Example                          |
|-----------|--------------------------------------------|----------------------------------|
| `group`   | Currently selected group name              | `?group=production-services`     |
| `asset`   | Currently highlighted asset within a group | `?group=production&asset=api-gw` |

When no `group` parameter is present (or it is set to `__ungrouped__`), the All Assets flat
table is shown.


## Related Features

- **SLO Registry** -- SLO definitions are linked to asset groups. The registry sidebar uses
  asset groups and datasources for filtering and navigation. See the SLO Registry documentation
  for details on linking SLOs to groups.
- **Navigator** -- The Navigator page reuses the asset group tree for selecting which assets
  to display in the heatmap view.
- **Evaluations** -- When triggering an evaluation, assets are selected from the global asset
  list. Evaluation results are scoped to individual assets within a group.
- **SLO Groups** -- Template-based SLO generation configurations that automatically create
  SLO definitions for assets in a group based on a template.
