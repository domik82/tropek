# Asset Group Management on the SLO Registry Page

**Date:** 2026-03-16
**Status:** Approved
**Scope:** UI + backend changes for managing asset groups and their SLO links from the SLO Registry page

## Context

The SLO Registry page currently shows a single-column list of SLO definition cards. Asset groups exist in the backend (`POST/GET/PUT/DELETE /asset-groups`, `POST/DELETE /asset-groups/{name}/slo-links`) but have no UI management surface. This spec adds group CRUD, bidirectional SLO linking, and filtered views to the SLO Registry page.

### Related specs

- SLO format refactor: `docs/superpowers/specs/2026-03-15-ui-slo-format-refactor-design.md` (prerequisite, already approved)

### Existing backend shapes

```
AssetGroupCreate:  { name, display_name?, description?, members[], subgroups[] }
AssetGroupRead:    { id, name, display_name?, description?, members[], subgroups[], created_at, updated_at }
AssetGroupSLOLink: { group_name, slo_name, sli_name, data_source_name }
AssetGroupTreeResponse: { top_level: AssetGroupRead[], all_groups: AssetGroupRead[] }
```

## Decisions

| Decision | Rationale |
|---|---|
| Groups live on the SLO Registry page, not a separate page | Groups are metadata for SLOs — colocating them reduces navigation |
| Persistent 180px left sidebar with group tree | Simple, always visible, narrow enough to not steal space from the SLO list |
| Bidirectional linking (from group side and SLO side) | Both workflows are natural — "add SLOs to this group" and "add this SLO to a group" |
| Shared link dialog component | One dialog with pre-filled fields depending on entry point |
| Datasource selected first, then SLI filtered by adapter_type | People think "I want to monitor from Prometheus" before "which queries" |
| Unique constraint `(group_name, slo_name)` on links | One link per SLO per group; different environments need distinct SLO names |
| SLI definitions get `adapter_type` field | Enables filtering SLIs by datasource type in the link dialog |
| POC migration strategy: regenerate clean `001`, keep manual `002` | No production data to preserve; single clean schema migration |
| Delete dialog: radio selection + confirmation modal | Safer than two action buttons — forces deliberate choice |
| Extract `GroupTreeRenderer` from `AssetGroupCard` | Same tree traversal + collapse logic reused for asset tree and SLO group tree |

## 1. Page Layout

The SLO Registry page becomes a two-panel layout:

```
┌──────────┬─────────────────────────────────────────┐
│ Groups   │  SLO Registry                           │
│ (180px)  │  Showing: All SLOs (12)     [+ Create]  │
│          │                                         │
│ All SLOs │  ▸ response-time-slo  v3 active  +Group │
│ Prod APIs│  ▸ error-rate-slo     v2 active  +Group │
│  Payment │  ▸ throughput-slo     v1 active  +Group │
│  Auth    │  ▸ old-latency-slo    v1 inactive+Group │
│ Staging  │                                         │
│ Mobile   │                                         │
│  iOS     │                                         │
│  Android │                                         │
│          │                                         │
│ Ungrouped│                                         │
└──────────┴─────────────────────────────────────────┘
```

### Sidebar (180px, left)

- **Header:** "Asset Groups" title + "+ New" button (opens create dialog)
- **Search:** Filterable text input to narrow the group tree
- **Tree:** Recursive `GroupTreeRenderer` nodes with expand/collapse and SLO count badges
- **Special nodes:**
  - "All SLOs" at top — clears filter, shows all SLOs (highlighted when active)
  - "Ungrouped" at bottom — filters to SLOs with zero group links
- **Interactions:** Click a group to select it (filters SLO list). Right-click or hover menu for Edit / Delete / Add SLO link.

### Main content (remaining width)

- **Header:** "SLO Registry" + filter indicator ("Showing: Production APIs (3)") + "+ Create SLO" button
- **SLO cards:** Existing accordion cards, plus:
  - Group tag(s) shown on the right side of each card row
  - "+ Group" button on each card (opens `SloLinkDialog` with SLO pre-filled)

## 2. SLO List Filtering

When a group is selected in the sidebar:

1. **Filtered state:** SLO list shows only SLOs linked to that group. Header updates to "Showing: Production APIs (3)".
2. **"Show all" toggle:** A link below the header — "Show all SLOs". When active, unlinked SLOs reappear at reduced opacity; linked SLOs stay full brightness.
3. **"All SLOs" node:** Clicking it clears the filter entirely.
4. **"Ungrouped" node:** Filters to SLOs with zero group links.
5. **URL state:** Selected group stored in query param (`?group=production-apis`) so the filter survives page refresh.

## 3. GroupTreeRenderer — Extracted Component

Extract the recursive tree traversal and collapse logic from `AssetGroupCard` into a generic renderer:

```typescript
interface GroupTreeRendererProps {
  group: AssetGroup
  tree: AssetGroupTree
  filterQuery: string
  renderNode: (group: AssetGroup, isOpen: boolean) => ReactNode
  renderLeaves?: (group: AssetGroup) => ReactNode
  onSelect?: (groupName: string) => void
  selectedGroup?: string | null
  forceExpanded?: boolean
  indent?: number
}
```

- `renderNode` — renders the header for each group node (label, count, expand arrow)
- `renderLeaves` — optional, renders leaf content inside the collapsible (asset members or SLO links)
- `onSelect` — click handler for group selection (sidebar use case)
- The component handles: recursive subgroup resolution from `tree.all_groups`, expand/collapse state, filter-based visibility, indentation

**Consumers:**
- `AssetGroupCard` refactored to use `GroupTreeRenderer` with asset-specific `renderNode`/`renderLeaves`
- `GroupSidebar` uses `GroupTreeRenderer` with SLO-group-specific `renderNode` and `onSelect`

## 4. Group CRUD Dialogs

All dialogs use the existing `Dialog` component from `ui/src/components/ui/dialog.tsx`.

### 4a. Create Group Dialog

Opened from "+ New" button in sidebar header.

**Fields:**
- `name` — required, slug format (lowercase, hyphens)
- `display_name` — optional, human-readable label
- `description` — optional, textarea
- `parent_group` — optional combobox, filterable list of existing groups. "None (top-level)" by default.

**API:** `POST /asset-groups` with optional `subgroups` on the parent if a parent is selected (via `POST /asset-groups/{parent}/subgroups`).

### 4b. Edit Group Dialog

Opened from group context menu (right-click / hover) in sidebar.

**Fields:**
- `name` — read-only (displayed but not editable)
- `display_name` — editable
- `description` — editable
- `parent_group` — editable combobox (allows re-parenting)
- **Linked SLOs list** — read-only list of current links with inline unlink (✕ button per link). Each row shows: `slo_name → sli_name`. Clicking ✕ calls `DELETE /asset-groups/{name}/slo-links/{link_name}`.

**API:** `PATCH /asset-groups/{name}` for property changes. Unlink via individual DELETE calls.

### 4c. Delete Group Dialog

Opened from group context menu in sidebar.

**Flow:**
1. Dialog shows group name, linked SLO count, and subgroup count
2. Two radio options (neither selected by default):
   - **"Delete & Keep SLOs Active"** — group and subgroups are deleted, all linked SLOs remain active and become ungrouped
   - **"Delete & Deactivate SLOs"** — group and subgroups are deleted, all linked SLOs are marked inactive
3. Delete button is disabled until a radio is selected
4. Clicking Delete opens a **confirmation modal**: "Are you sure? This will delete [group name] and [keep N SLOs active / deactivate N SLOs]."
5. Confirming executes the action

**API:** `DELETE /asset-groups/{name}?deactivate_slos=true|false` (backend needs to support this query parameter).

## 5. SLO Link Dialog

A shared dialog component used from both entry points.

### Entry point A: From SLO card ("+ Group" button)

- SLO field pre-filled and locked
- User selects: datasource → SLI (filtered) → group
- Calls `POST /asset-groups/{group}/slo-links`

### Entry point B: From group context menu ("Add SLO" action)

- Group field pre-filled and locked
- User selects: datasource → SLI (filtered) → SLO
- Calls `POST /asset-groups/{group}/slo-links`

### Combobox chain

1. **Datasource** — `GET /datasources` → filterable list showing `name` and `adapter_type` badge
2. **SLI** — `GET /sli-definitions?adapter_type={selected_datasource.adapter_type}` → filterable list, disabled until datasource is selected (greyed out with "Select datasource first...")
3. **Group or SLO** — `GET /asset-groups` or `GET /slo-definitions` → filterable list

### Validation

- If `(group_name, slo_name)` pair already exists, the Link button is disabled with message: "This SLO is already linked to this group"
- Backend returns 409 Conflict for duplicate links

## 6. Backend Changes

### 6a. Add `adapter_type` to SLI definitions

**Model change:** Add non-nullable `adapter_type: str` column to the SLI definitions table.

**Schema changes:**
```python
class SLIDefinitionCreate(BaseModel):
    name: str
    adapter_type: str              # NEW — e.g. "prometheus", "dynatrace", "splunk"
    display_name: str | None = None
    indicators: dict[str, str]
    notes: str | None = None
    author: str | None = None
    meta: dict[str, Any] = {}

class SLIDefinitionRead(BaseModel):
    # ... existing fields ...
    adapter_type: str              # NEW
```

**Endpoint change:** `GET /sli-definitions` gains `?adapter_type=X` query parameter to filter results.

### 6b. Unique constraint on SLO links

Add `UNIQUE (group_name, slo_name)` constraint to the `asset_group_slo_links` table (or equivalent, depending on column names in the model).

The API returns **409 Conflict** when a duplicate `(group_name, slo_name)` link is attempted.

### 6c. Delete group with deactivation option

`DELETE /asset-groups/{name}` gains `?deactivate_slos=bool` query parameter (default `false`). When `true`, all SLOs linked to the group (and its subgroups, recursively) are marked inactive before the group is deleted.

### 6d. Migration strategy (POC)

- Delete `001_initial_schema.py` and `63404ff4de0e_slo_format_redesign.py`
- Autogenerate fresh `001` from current SQLAlchemy models (includes `adapter_type`, unique constraint)
- Keep `002_timescaledb_hypertable_and_seed_data.py` unchanged (manual migration, separate concern)

## 7. Parallel Implementation Tracks

```
Track A (Backend)                    Track B (UI — Sidebar + CRUD)
─────────────────                    ─────────────────────────────
1. adapter_type on SLI model         1. Extract GroupTreeRenderer
2. ?adapter_type filter on GET       2. GroupSidebar component
3. Unique (group,slo) constraint     3. Create/Edit/Delete dialogs
4. ?deactivate_slos on DELETE        4. Group context menu
5. Migration reset (001 regen)
                    ╲                ╱
                     ╲              ╱
                      ╲            ╱
              Track C (UI — Linking + Filtering)
              ──────────────────────────────────
              1. SloLinkDialog component
              2. "+ Group" button on SLO cards
              3. SLO list filtering by group
              4. "Show all" toggle
              5. URL param sync (?group=X)
```

Tracks A and B are fully independent and can be built in parallel. Track C depends on both A and B being complete.

## 8. Component Summary

| Component | New/Modified | Location |
|---|---|---|
| `GroupTreeRenderer` | **New** | `ui/src/components/GroupTreeRenderer.tsx` |
| `GroupSidebar` | **New** | `ui/src/features/slos/components/GroupSidebar.tsx` |
| `GroupCreateDialog` | **New** | `ui/src/features/slos/components/GroupCreateDialog.tsx` |
| `GroupEditDialog` | **New** | `ui/src/features/slos/components/GroupEditDialog.tsx` |
| `GroupDeleteDialog` | **New** | `ui/src/features/slos/components/GroupDeleteDialog.tsx` |
| `SloLinkDialog` | **New** | `ui/src/features/slos/components/SloLinkDialog.tsx` |
| `AssetGroupCard` | **Modified** | Refactored to use `GroupTreeRenderer` |
| `SloRegistryPage` | **Modified** | Two-panel layout, group filter state, URL param sync |

## 9. Future Enhancements (Out of Scope)

- **Duplicate SLO action** — clone an SLO definition with a new name to ease bulk creation across environments (e.g., creating `error-rate-prod`, `error-rate-uat`, `error-rate-staging` from a template)
- **Collapsible sidebar** — evolve from persistent 180px to a collapsible icon rail (option C from brainstorming) if horizontal space becomes a concern
