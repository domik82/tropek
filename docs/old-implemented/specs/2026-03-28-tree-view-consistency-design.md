# Tree View Consistency Redesign

**Date:** 2026-03-28
**Status:** Approved

## Problem

The tree view is used in three places (Navigator, Assets, SLO Registry) but was built inconsistently:

- **Font sizes differ**: Navigator uses 14px groups / 13px assets; Registry uses 12px everywhere
- **Row heights differ**: ~32px vs ~24px
- **Filter inputs differ**: Navigator has clear X button; Registry doesn't. Different padding/sizing.
- **Sidebar widths differ**: Both claim 260px but Registry filter stretches wider visually
- **No type icons**: Nodes are text-only (Navigator) or color-coded-only (Registry)
- **No group/asset colors**: No visual identity for groups or critical assets
- **Chevron behavior differs**: Navigator uses rotation animation; Registry swaps icons
- **Selection state differs**: Both use primary green left border, but no group-aware selection
- **Font family inconsistent**: Some nodes use monospace; CLAUDE.md says sidebar chrome should be sans-serif

## Design Decisions

### 1. Unified Dimensions

All tree views share identical sizing:

| Property | Value | Rationale |
|---|---|---|
| Font size | 14px, all nodes | Carbon/Fluent UI consensus |
| Font family | `system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif` | CLAUDE.md: sans-serif for UI chrome |
| Icon size | 16px | Readability at sidebar scale |
| Chevron size | 12px | Fluent UI / Primer standard |
| Row height | 32px | Carbon default / Fluent medium |
| Indent per level | 24px | Fluent UI medium indentation |
| Leaf offset | +16px (chevron width) | Carbon: align labels when no chevron |
| Sidebar width | 260px fixed, all pages | Current value, enforced consistently |
| Group font weight | 600 | Visually distinguish expandable groups |
| Leaf font weight | 400 (regular) | Normal weight for child nodes |

**Vertical alignment**: 16px icon with 14px font. Font uses `line-height: 16px` so it sits 1px from top and 1px from bottom of the icon. Both centered in 32px row via `align-items: center`. Result: 8px padding top + 16px content + 8px padding bottom = 32px.

### 2. Entity Icon Mapping

Every tree node gets a Lucide icon at 16px. Icons provide instant visual type recognition.

#### Tree structure icons

| Entity | Lucide Icon | Color | Notes |
|---|---|---|---|
| Asset Group | `Folder` | Per-group custom color | Tinted with group's assigned color |
| "All" row | `LayoutGrid` | theme `--primary` | Aggregate view |
| "Ungrouped" | `Folder` (dimmed) | `#8b949e` at 50% opacity | Italic label, crossed-out folder |

#### Registry entity icons

| Entity | Lucide Icon | Color | Notes |
|---|---|---|---|
| SLO | `ShieldCheck` | `#7dc540` green | Quality gate = protection |
| SLI / Indicator | `Braces` | `#a371f7` purple | Query/expression definition |
| Datasource | `Database` | `#58a6ff` blue | Metric source (blue, not gray) |

#### Asset type icons

Each asset type maps to a specific icon. Assets without a recognized type use the fallback.

| Asset Type | Lucide Icon | Notes |
|---|---|---|
| `vm` | `Server` | Virtual machine |
| `service` | `Component` | Software service (4 diamonds) |
| `database` | `Database` | Data store (gray `#8b949e`, not blue) |
| `container` | `Container` | Docker/shipping container grid |
| `endpoint` | `Laptop` | API endpoint |
| `load-test` | `Gauge` | Performance/load test (NEW type) |
| fallback | `CircuitBoard` | Any unknown/custom type |

Default asset icon color is `#8b949e` (muted). Assets with a custom color assigned get their icon stroke and label text tinted to that color.

### 3. Group Colors (DB change)

**New column**: `color` on `asset_groups` table — nullable `VARCHAR`, hex string like `#6897BB`.

- **Auto-assigned** randomly from a curated palette on group creation
- **Editable** later via group settings (color picker or palette selection)
- **Palette** (8-10 curated colors for dark backgrounds):
  `#6897BB`, `#E8915A`, `#A371F7`, `#7DC540`, `#F85149`, `#58A6FF`, `#D4A032`, `#2DD4A0`, `#DB61A2`, `#8B949E`
- **Where it appears**: Tints the `Folder` icon stroke color

### 4. Asset Colors (DB change)

**New column**: `color` on `assets` table — nullable `VARCHAR`, hex string.

- **Default**: `NULL` — uses standard muted gray `#8b949e`
- **Purpose**: Mark critical or important assets with a color so they visually pop
- **Where it appears**: Tints the asset's type icon stroke and label text
- **Assignment**: Manual only (via asset settings), not auto-assigned

### 5. Asset Type: `load-test` (DB change)

Add `load-test` to the seed data in migration. Insert alongside existing types (`vm`, `service`, `database`, `container`, `endpoint`).

### 6. Selection State

**Group nodes**: Selection uses the group's own color.
- Left border: `2px solid {groupColor}`
- Background: `{groupColor}` at 12% opacity
- Count badge: tints to group color

**Non-group nodes** (assets, SLOs, SLIs, datasources): Selection uses theme primary.
- Left border: `2px solid var(--primary)`
- Background: `var(--primary)` at 12% opacity

**Hover** (all nodes): `bg-muted/50` (unchanged from current).

### 7. Unified Filter Input

Identical filter component used on all pages (Navigator, Assets, SLO Registry):

- Search icon (left, 14px, `text-muted-foreground`)
- Clear X button (right, appears when text is present)
- Match count below input when filtering (e.g., "3 results")
- Padding: `py-1.5 px-8` (left for icon, right for X)
- Font: 13px
- Background: `bg-input`, border: `border-border`, radius: `rounded-md`
- Auto-expands matching parent nodes
- Highlights matched text in labels (optional — nice to have)

### 8. Badge Format

Two distinct badge styles, used consistently across all trees:

- **Count badge** (groups): Filled dark pill (`bg: #30363d`, `color: #c9d1d9`, `font-size: 10px`, `font-weight: 600`, `min-width: 18px`, `height: 18px`, `border-radius: 99px`). Shows child count.
- **Version tag** (SLOs): Outlined rectangular tag (`border: 1px solid #30363d`, `color: #8b949e`, `font-size: 10px`, `padding: 1px 6px`, `border-radius: 4px`). Shows version like `v2`.
- **No badge**: Leaf nodes (assets, SLIs, datasources) have no badge.

### 9. "All" Row

All tree views include an "All" row at the top for consistency:

- Navigator/Assets: "All" with `LayoutGrid` icon (existing)
- Registry: "All SLOs", "All Datasources", "All Assets" depending on active tab

### 10. Chevron Behavior

All trees use the same interaction:

- Icon: `ChevronRight` from Lucide (12px)
- Expand: 90° rotation animation (CSS `transform: rotate(90deg)` with transition)
- No icon swap — rotation only
- **Hidden** (not removed) on leaf nodes to preserve label alignment
- **Separate click zones**: chevron for expand/collapse, label area for selection (Carbon/Fluent standard)

## Component Architecture

### Shared `TreeNode` component

A single `TreeNode` component renders all node types across all trees. It accepts:

- `icon`: Lucide icon component
- `iconColor`: hex string (from entity type, group color, or asset color)
- `label`: display text
- `badge`: optional right-side badge (count, version tag)
- `depth`: indentation level
- `isExpandable`: shows chevron
- `isExpanded`: chevron rotation state
- `isSelected`: selection highlight
- `selectionColor`: hex string (group color or primary)

### Shared `TreeFilter` component

A single filter input component used in all sidebar headers. Accepts:

- `value` / `onChange`: controlled input
- `placeholder`: e.g., "Filter groups & assets..." or "Filter..."
- `resultCount`: optional number shown below input when filtering

### Icon resolver

A utility mapping entity/asset types to Lucide icons:

```typescript
const ASSET_TYPE_ICONS: Record<string, LucideIcon> = {
  vm: Server,
  service: Component,
  database: Database,
  container: Container,
  endpoint: Laptop,
  'load-test': Gauge,
}
const FALLBACK_ASSET_ICON = CircuitBoard

const ENTITY_ICONS = {
  slo: ShieldCheck,
  sli: Braces,
  datasource: Database, // blue variant
  group: Folder,
  all: LayoutGrid,
}
```

## Scope

### In scope (this spec)

- Unified TreeNode and TreeFilter components
- Icon mapping for all entity and asset types
- Consistent dimensions across all tree views
- Group color column + auto-assignment + folder icon tinting
- Asset color column + icon/label tinting
- `load-test` asset type seed
- Selection state with group-aware coloring
- Chevron rotation animation (unified)

### Out of scope

- Drag-to-resize sidebar (fixed 260px for now)
- Color picker UI for group/asset editing (use simple input or predefined palette)
- Max child node limits
- Keyboard navigation / accessibility improvements (future)
- Tree connecting lines / indent guides (future)
- Material Symbols migration (staying with Lucide)

## Visual References

Mockups from this brainstorming session are in `.superpowers/brainstorm/69756-1774692440/content/`:

- `current-inconsistencies.html` — side-by-side comparison of current problems
- `group-color-options.html` — A/B/C/D options for group color placement (picked A)
- `slo-tree-icons.html` — full icon set in SLO tree context
- `asset-type-icons-v3.html` — final asset type icon mapping with tree preview
- `selection-state.html` — B vs C selection styles (picked C)
- `icon-size-comparison.html` — 14-18px icon size comparison (picked 16px)

## Design References

- IBM Carbon Tree View usage guidelines: `docs/ui-references/carbon/`
- Ant Design Tree component: `docs/ui-references/ant-design/` (not read — available for detail questions)
- Fluent UI 2 tree indentation and selection patterns (referenced via screenshots)
- `docs/ui-improvements/tree-view-approaches.md` — 10-system comparison study
- `docs/ui-improvements/color-palette-guide.md` — dark mode palette methodology
