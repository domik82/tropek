# Theme System

TROPEK uses a CSS custom property system with three theme variants, controlled by a
`data-theme` attribute on the `<html>` element. All colours in the UI are assigned by
function (surface, border, status, action) rather than by hue.

## Themes

| Theme | `data-theme` value | Colour system | Status |
|---|---|---|---|
| Dark | `dark` | Radix UI colour scales (slate, green, grass, red, yellow, sky, amber) | Primary, fully implemented |
| Alt (current) | `current` | Tailwind slate scale with hardcoded hex accents | Fully implemented |
| Light | `light` | Radix light scales (planned) | Stub -- only meta-timeline palette defined |

Both `dark` and `current` are considered dark themes (`isDark = true`). The light theme
is not exposed in the UI toggle -- the navbar only shows "Dark" and "Alt" buttons.

## Key files

| File | Purpose |
|---|---|
| `ui/src/index.css` | CSS custom properties per theme, Tailwind token registration, component overrides |
| `ui/src/lib/theme-context.tsx` | `ThemeProvider` and `useTheme` hook (React context) |
| `ui/src/lib/theme.ts` | `Theme` type, ECharts-only hex colour maps (`RESULT_COLOUR`, `CHART_THEME`) |
| `ui/src/lib/theme-utils.ts` | Font size clamping utility (12-24px range) |
| `ui/src/lib/status.ts` | Tailwind class constants for evaluation status colours |
| `ui/src/lib/entity-colors.ts` | Entity identity colour constants and group palette |

## ThemeProvider and useTheme

`ThemeProvider` wraps the entire app (outermost provider in `App.tsx`). It manages two
pieces of state persisted in `localStorage`:

- **Theme** (`tropek-theme` key, default: `dark`) -- sets `data-theme` attribute on
  `document.documentElement` and toggles the `.dark-theme` class (needed for Radix CSS imports).
- **Font size** (`tropek-font-size` key, default: 18px) -- sets root `fontSize`, clamped
  to 12-24px.

The `useTheme()` hook returns:

```typescript
interface ThemeCtx {
  theme:       Theme          // 'current' | 'dark' | 'light'
  setTheme:    (t: Theme) => void
  isDark:      boolean        // true for both 'dark' and 'current'
  fontSize:    number
  setFontSize: (n: number) => void
}
```

## CSS custom properties

### Three-layer architecture

1. **Layer 1 -- Theme definitions** (`[data-theme="dark"]`, `[data-theme="current"]` blocks
   in `index.css`). These define functional aliases like `--surface-base`, `--status-pass`,
   `--action-primary` with theme-specific values.

2. **Layer 2 -- Tailwind registration** (the `@theme inline` block in `index.css`). Maps
   functional aliases to `--color-*` tokens, enabling Tailwind utility classes like
   `bg-surface-raised`, `text-pass`, `border-subtle`.

3. **Layer 3 -- JS hex constants** (`RESULT_COLOUR` and `CHART_THEME` in `theme.ts`).
   ECharts cannot resolve CSS custom properties, so chart code uses these hardcoded hex
   maps instead. Only ECharts code should use layer 3.

Components should always use Tailwind utilities (layer 2). Direct `var()` references to
layer 1 tokens are acceptable in custom CSS but should not appear in inline styles when
a Tailwind class exists.

### Token categories

| Category | Tokens | Example usage |
|---|---|---|
| Surface (5) | `--surface-base`, `--surface-raised`, `--surface-overlay`, `--surface-sunken`, `--surface-inset` | Page bg, cards, popovers, inset areas |
| Border (4) | `--border-default`, `--border-subtle`, `--border-strong`, `--border-input` | Standard/emphasized borders, form inputs |
| Text (4) | `--text-primary`, `--text-secondary`, `--text-muted`, `--text-inverse` | Main text, secondary, placeholders, text on primary bg |
| Actions (11) | `--action-primary-*`, `--action-secondary-*`, `--action-destructive-*` | Buttons, interactive elements |
| State (6) | `--state-disabled-*`, `--state-focus-ring`, `--state-selected-bg`, `--state-hover-bg` | Disabled, focus, selection, hover states |
| Links (2) | `--link`, `--link-hover` | Hyperlinks |
| Status (7) | `--status-pass`, `--status-warning`, `--status-fail`, `--status-error`, `--status-invalidated` + bg variants | Evaluation outcomes |
| Entity (5) | `--entity-slo`, `--entity-sli`, `--entity-datasource`, `--entity-group`, `--entity-asset` | Entity type identity in trees, badges |
| Sidebar/Tree (6) | `--sidebar-bg`, `--sidebar-border`, `--tree-selected-*`, `--tree-hover-bg`, `--tree-node-icon` | Navigation sidebar |
| Table (6) | `--table-header-bg`, `--table-row-*`, `--table-border` | Data tables |
| Heatmap (5) | `--heatmap-bg`, `--heatmap-cell-*`, `--heatmap-text`, `--heatmap-selection-ring` | Evaluation heatmaps |
| Chart (5) | `--chart-bg`, `--chart-border`, `--chart-grid`, `--chart-axis-text`, `--chart-series-line` | Chart chrome (CSS context only) |
| Labels/Chips (15) | `--chip-tag-*`, `--chip-var-*`, `--chip-filter-*`, `--label-*` | Tag pills, variable chips, filter badges |
| Forms (5) | `--input-bg`, `--input-border`, `--input-focus`, `--input-error`, `--input-placeholder` | Form controls |
| Indicators (3) | `--indicator-note`, `--indicator-key-sli`, `--indicator-default` | Annotation markers, key SLI badges |
| Destructive form (4) | `--destructive-form-bg`, `--destructive-form-border`, `--destructive-form-stripe`, `--destructive-form-text` | Delete confirmation forms |

## TROPEK logo colour

The brand colour is a fixed constant that never changes with theme:

```css
:root {
  --tropek-logo: oklch(68.628% 0.185 148.958);
}
```

## Radix colour scales (dark theme)

The dark theme imports these Radix UI dark colour scales:

| Scale | Usage |
|---|---|
| `slate` | Surfaces, borders, text hierarchy, neutral UI chrome |
| `green` / `grass` | Pass status, SLO entity colour, default indicator |
| `red` | Fail status, destructive actions |
| `yellow` | Warning status |
| `sky` | Primary actions, links, datasource entity, key SLI indicator |
| `amber` | Note indicator, variable chips, warning-adjacent accents |
| `gray` | Sunken surfaces, alternative table rows |
| `blue` | Raised surfaces (blue-2), chart series |
| `lime` | (imported but minimal direct usage) |

The `current` (Alt) theme does not use Radix scales. It uses Tailwind's built-in slate
palette (`var(--color-slate-*)`) and hardcoded hex values for accents.

## Status colours vs action accent colours

These two colour systems serve different purposes and must not overlap.

**Status colours** represent evaluation outcomes. Use the Tailwind utilities `text-pass`,
`text-warning`, `text-fail`, `text-status-error`, `text-invalidated` (and their `bg-` variants).
These appear in heatmaps, result badges, score text, and SLI breakdown tables.

```tsx
<span className="text-pass">91.5</span>
<div className="bg-status-pass-bg rounded px-2">Pass</div>
```

**Action accent colours** represent action identity in context menus and forms. These are
intentionally hardcoded (gray `#8B949E`, red `#F85149`, blue `#58A6FF`, purple `#A371F7`)
and must not be confused with status colours.

**Interactive elements** (buttons, selected states, links) use the `--primary` / `--action-primary`
token family, which is theme-aware. Never hardcode button colours.

## How to add a new theme

1. Add the theme name to the `Theme` type in `ui/src/lib/theme.ts`.

2. Add a `[data-theme="your-theme"]` block in `ui/src/index.css` defining all functional
   tokens. Copy the `dark` theme block as a template -- it has every token defined.

3. Add entries in `RESULT_COLOUR` and `CHART_THEME` in `ui/src/lib/theme.ts` with the
   hex values ECharts will use for that theme.

4. Update `ThemeProvider` in `ui/src/lib/theme-context.tsx`:
   - Add the new theme string to the `stored ===` check in the initializer.
   - If the theme is light, the `isDark` logic (`theme !== 'light'`) may need updating.

5. Add a toggle button in the navbar (`App.tsx` NavControls section).

## How to modify existing tokens

- **Changing a colour across one theme**: edit the value in that theme's
  `[data-theme="..."]` block in `index.css`. No other changes needed unless the token
  is also used by ECharts, in which case update the hex value in `theme.ts` too.

- **Adding a new token**: define it in every theme block in `index.css`, register it in
  the `@theme inline` block (with a `--color-` prefix for Tailwind), then use the
  resulting Tailwind utility class in components.

- **Renaming a token**: update the CSS variable name in all theme blocks, the `@theme inline`
  mapping, and all component references. Search for both the CSS variable name and the
  Tailwind class name (e.g., `--status-pass` and `text-pass`).

## Light theme status

The light theme is a stub. Only the meta-timeline cycling palette and focus-eval-marker
tokens are defined in the `[data-theme="light"]` block. All other functional tokens
(surfaces, borders, text, status, actions, etc.) are undefined, so the theme is
non-functional. The "Alt"/"Dark" toggle in the navbar deliberately omits a Light button.

To complete the light theme, import Radix light colour scales (without the `-dark` suffix),
define all token categories in the `[data-theme="light"]` block, and update `RESULT_COLOUR`
and `CHART_THEME` in `theme.ts` with appropriate light-mode hex values.
