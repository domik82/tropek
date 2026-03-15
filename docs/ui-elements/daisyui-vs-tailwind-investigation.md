# DaisyUI vs Bare Tailwind — Codebase Investigation Guide

## Context

The project currently uses (or is considering) the daisyUI `forest` theme via:

```css
@plugin "daisyui" {
  themes: light --default, dark --prefersdark;
}

@plugin "daisyui/theme" {
  name: "forest";
  default: true;
  prefersdark: true;
  color-scheme: "dark";
  --color-base-100: oklch(20.84% 0.008 17.911);
  --color-base-200: oklch(18.522% 0.007 17.911);
  --color-base-300: oklch(16.203% 0.007 17.911);
  --color-base-content: oklch(83.768% 0.001 17.911);
  --color-primary: oklch(68.628% 0.185 148.958);
  --color-primary-content: oklch(0% 0 0);
  --color-secondary: oklch(69.776% 0.135 168.327);
  --color-secondary-content: oklch(13.955% 0.027 168.327);
  --color-accent: oklch(70.628% 0.119 185.713);
  --color-accent-content: oklch(14.125% 0.023 185.713);
  --color-neutral: oklch(30.698% 0.039 171.364);
  --color-neutral-content: oklch(86.139% 0.007 171.364);
  --color-info: oklch(72.06% 0.191 231.6);
  --color-info-content: oklch(0% 0 0);
  --color-success: oklch(64.8% 0.15 160);
  --color-success-content: oklch(0% 0 0);
  --color-warning: oklch(84.71% 0.199 83.87);
  --color-warning-content: oklch(0% 0 0);
  --color-error: oklch(71.76% 0.221 22.18);
  --color-error-content: oklch(0% 0 0);
  --radius-selector: 0.25rem;
  --radius-field: 1rem;
  --radius-box: 1rem;
  --size-selector: 0.21875rem;
  --size-field: 0.28125rem;
  --border: 1px;
  --depth: 0;
  --noise: 0;
}
```

The goal is to evaluate whether to **keep daisyUI**, **drop it entirely**, or **keep only the theme tokens** — without introducing unnecessary third-party dependencies.

---

## What daisyUI actually does (two separate layers)

### Layer 1 — Theme tokens (`@plugin "daisyui/theme"`)

This writes CSS custom properties (variables) onto `:root`. Nothing more. It is equivalent to:

```css
:root {
  --color-primary: oklch(68.628% 0.185 148.958);
  --color-base-100: oklch(20.84% 0.008 17.911);
  /* ...etc */
}
```

Tailwind v4 can do the same natively with `@theme {}`. No library needed for this part.

### Layer 2 — Component classes (`@plugin "daisyui"`)

This generates CSS class names like `btn`, `badge`, `input`, `toggle`, `checkbox`, `alert`, `card`, etc.

These are **pure CSS classes** — not React/Vue components. They are applied directly in HTML:

```html
<button class="btn btn-primary">Click me</button>
<span class="badge badge-success">Done</span>
<input class="input input-bordered" />
```

DaisyUI generates all the styling rules for these classes internally, reading the CSS variables from Layer 1. So `btn-primary` works because it references `--color-primary` under the hood.

**This is what you cannot trivially replace** — if the codebase uses these class names, dropping daisyUI means manually rewriting those styles with raw Tailwind utilities.

---

## Investigation tasks for Claude Code

### 1. Scan for daisyUI component class usage

Search the entire codebase for usage of daisyUI component class names in templates, JSX, HTML files.

**Classes to search for** (non-exhaustive — extend if needed):

```
btn, badge, input, select, textarea, toggle, checkbox, radio,
alert, card, modal, drawer, navbar, menu, tab, tabs,
avatar, tooltip, progress, loading, skeleton, divider,
collapse, carousel, chat, countdown, diff, dock,
dropdown, fieldset, file-input, filter, join, kbd,
label, link, list, mask, mockup, range, rating,
stack, stat, stats, steps, swap, table, timeline,
toast, validator
```

**Questions to answer:**
- Are any of these class names present in `.html`, `.jsx`, `.tsx`, `.vue`, `.svelte` files?
- How many unique daisyUI component classes are actually used?
- Which files use them?

### 2. Check CSS/style files for daisyUI dependency

- Is `@plugin "daisyui"` present in any `.css` file?
- Is `daisyui` listed in `package.json` dependencies?
- Is there a `tailwind.config.*` file using `require('daisyui')`?

### 3. Determine the recommendation

Based on findings, recommend one of:

#### Option A — Keep daisyUI as-is
**When:** The codebase uses many daisyUI component classes (`btn`, `badge`, `card`, etc.).  
**Action:** Keep both `@plugin` blocks. No changes needed.

#### Option B — Drop daisyUI entirely, use bare Tailwind tokens
**When:** The codebase does NOT use any daisyUI component class names — only the color palette matters.  
**Action:** Remove both `@plugin` blocks. Replace with:

```css
@import "tailwindcss";

@theme {
  --color-base-100: oklch(20.84% 0.008 17.911);
  --color-base-200: oklch(18.522% 0.007 17.911);
  --color-base-300: oklch(16.203% 0.007 17.911);
  --color-base-content: oklch(83.768% 0.001 17.911);
  --color-primary: oklch(68.628% 0.185 148.958);
  --color-primary-content: oklch(0% 0 0);
  --color-secondary: oklch(69.776% 0.135 168.327);
  --color-secondary-content: oklch(13.955% 0.027 168.327);
  --color-accent: oklch(70.628% 0.119 185.713);
  --color-accent-content: oklch(14.125% 0.023 185.713);
  --color-neutral: oklch(30.698% 0.039 171.364);
  --color-neutral-content: oklch(86.139% 0.007 171.364);
  --color-info: oklch(72.06% 0.191 231.6);
  --color-info-content: oklch(0% 0 0);
  --color-success: oklch(64.8% 0.15 160);
  --color-success-content: oklch(0% 0 0);
  --color-warning: oklch(84.71% 0.199 83.87);
  --color-warning-content: oklch(0% 0 0);
  --color-error: oklch(71.76% 0.221 22.18);
  --color-error-content: oklch(0% 0 0);
  --radius-selector: 0.25rem;
  --radius-field: 1rem;
  --radius-box: 1rem;
}

@layer base {
  :root { color-scheme: dark; }
  body  { @apply bg-base-100 text-base-content; }
}
```

This gives full access to `bg-primary`, `text-base-content`, `border-success`, etc. — no library needed.

#### Option C — Keep only the theme plugin, drop component plugin
**When:** Some component classes are used but could be replaced incrementally.  
**Action:** Remove `@plugin "daisyui"`, keep `@plugin "daisyui/theme"` for now and migrate component classes one by one to raw Tailwind utilities.

#### Option D — Zero dependencies: own tokens + own components + light/dark support ⭐
**When:** Starting fresh or the codebase has few/no daisyUI component classes, and you want full control with proper light and dark theme switching.  
**Action:** Remove both `@plugin` blocks entirely. Define tokens twice (light defaults in `@theme`, dark overrides in `.dark {}`), then write your own component classes in `@layer components` that read from those tokens. Theme switching is a single JS line.

```css
@import "tailwindcss";

/* ─── Light theme tokens (default) ─────────────────────────────── */
@theme {
  --color-base-100: oklch(97% 0.003 17.911);
  --color-base-200: oklch(93% 0.004 17.911);
  --color-base-300: oklch(88% 0.005 17.911);
  --color-base-content: oklch(20% 0.008 17.911);

  --color-primary: oklch(55% 0.185 148.958);
  --color-primary-content: oklch(98% 0 0);
  --color-secondary: oklch(55% 0.135 168.327);
  --color-secondary-content: oklch(98% 0 0);
  --color-accent: oklch(55% 0.119 185.713);
  --color-accent-content: oklch(98% 0 0);
  --color-neutral: oklch(75% 0.039 171.364);
  --color-neutral-content: oklch(20% 0.008 171.364);

  --color-info: oklch(72.06% 0.191 231.6);
  --color-info-content: oklch(0% 0 0);
  --color-success: oklch(64.8% 0.15 160);
  --color-success-content: oklch(0% 0 0);
  --color-warning: oklch(84.71% 0.199 83.87);
  --color-warning-content: oklch(0% 0 0);
  --color-error: oklch(71.76% 0.221 22.18);
  --color-error-content: oklch(0% 0 0);

  --radius-selector: 0.25rem;
  --radius-field: 1rem;
  --radius-box: 1rem;
}

/* ─── Dark theme tokens (forest) — active when <html class="dark"> ─ */
@layer base {
  .dark {
    --color-base-100: oklch(20.84% 0.008 17.911);
    --color-base-200: oklch(18.522% 0.007 17.911);
    --color-base-300: oklch(16.203% 0.007 17.911);
    --color-base-content: oklch(83.768% 0.001 17.911);

    --color-primary: oklch(68.628% 0.185 148.958);
    --color-primary-content: oklch(0% 0 0);
    --color-secondary: oklch(69.776% 0.135 168.327);
    --color-secondary-content: oklch(13.955% 0.027 168.327);
    --color-accent: oklch(70.628% 0.119 185.713);
    --color-accent-content: oklch(14.125% 0.023 185.713);
    --color-neutral: oklch(30.698% 0.039 171.364);
    --color-neutral-content: oklch(86.139% 0.007 171.364);

    --color-info: oklch(72.06% 0.191 231.6);
    --color-info-content: oklch(0% 0 0);
    --color-success: oklch(64.8% 0.15 160);
    --color-success-content: oklch(0% 0 0);
    --color-warning: oklch(84.71% 0.199 83.87);
    --color-warning-content: oklch(0% 0 0);
    --color-error: oklch(71.76% 0.221 22.18);
    --color-error-content: oklch(0% 0 0);
  }

  :root {
    color-scheme: light;
  }

  .dark {
    color-scheme: dark;
  }

  body {
    @apply bg-base-100 text-base-content;
  }
}

/* ─── Your own component classes, reading from the tokens above ─── */
@layer components {
  /* Base button — shared structure */
  .btn {
    @apply inline-flex items-center justify-center gap-2 px-4 py-2
           font-semibold cursor-pointer transition-all select-none
           disabled:opacity-50 disabled:cursor-not-allowed;
    border-radius: var(--radius-field);
  }

  /* Variants */
  .btn-primary   { @apply bg-primary   text-primary-content   hover:brightness-110; }
  .btn-secondary { @apply bg-secondary text-secondary-content hover:brightness-110; }
  .btn-accent    { @apply bg-accent    text-accent-content    hover:brightness-110; }
  .btn-ghost     { @apply bg-transparent text-base-content hover:bg-neutral hover:text-neutral-content; }
  .btn-error     { @apply bg-error     text-error-content     hover:brightness-110; }

  /* Sizes */
  .btn-sm { @apply text-sm px-3 py-1; }
  .btn-lg { @apply text-lg px-6 py-3; }

  /* Badge */
  .badge {
    @apply inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium;
    border-radius: var(--radius-selector);
  }
  .badge-primary { @apply bg-primary text-primary-content; }
  .badge-success { @apply bg-success text-success-content; }
  .badge-warning { @apply bg-warning text-warning-content; }
  .badge-error   { @apply bg-error   text-error-content;   }

  /* Input */
  .input {
    @apply w-full px-3 py-2 bg-base-100 text-base-content border border-neutral
           focus:outline-none focus:border-primary transition-colors;
    border-radius: var(--radius-field);
  }

  /* Alert */
  .alert {
    @apply flex items-center gap-3 px-4 py-3;
    border-radius: var(--radius-box);
  }
  .alert-info    { @apply bg-info    text-info-content;    }
  .alert-success { @apply bg-success text-success-content; }
  .alert-warning { @apply bg-warning text-warning-content; }
  .alert-error   { @apply bg-error   text-error-content;   }

  /* Card */
  .card {
    @apply bg-base-200 p-4;
    border-radius: var(--radius-box);
  }
}
```

**Theme toggle — one line of JS:**

```js
document.documentElement.classList.toggle('dark')
```

**How it works end-to-end:**

1. `@theme {}` registers the light token values. Tailwind auto-generates `bg-primary`, `text-base-content`, `border-neutral`, etc. as utility classes.
2. `.dark {}` overrides those same variable names with dark values. Because every component reads the variable *by name* (not by value), they all flip automatically — you write the component once.
3. `@layer components {}` defines your own named classes (`.btn`, `.badge`, etc.) using those tokens. This is identical to what daisyUI does internally — you just own the code.
4. Toggling `class="dark"` on `<html>` is the only thing needed to switch themes.

> **Note on `color-scheme`:** Setting `color-scheme: dark` on `.dark` tells the browser to render native widgets (scrollbars, date pickers, `<select>`) in dark mode too. Don't skip it.

---

## Reference: bare Tailwind equivalents for common daisyUI components

If Option B or C is chosen, use these as starting points:

```html
<!-- btn btn-primary -->
<button class="bg-primary text-primary-content px-4 py-2 rounded-[--radius-field] font-semibold hover:brightness-110 transition-all cursor-pointer">
  Button
</button>

<!-- badge badge-success -->
<span class="bg-success text-success-content text-xs px-2 py-0.5 rounded-[--radius-selector] font-medium inline-flex items-center gap-1">
  Badge
</span>

<!-- input input-bordered -->
<input class="bg-base-100 border border-neutral text-base-content rounded-[--radius-field] px-3 py-2 w-full focus:outline-none focus:border-primary" />

<!-- alert alert-info -->
<div class="bg-info text-info-content px-4 py-3 rounded-[--radius-box] flex items-center gap-2">
  Alert message
</div>

<!-- toggle toggle-primary (requires a bit more CSS for the sliding part) -->
<!-- Recommend keeping daisyUI for toggle/checkbox/radio unless you enjoy pain -->
```

> **Note:** Simple components like `btn` and `badge` are easy to replicate.
> Complex stateful-looking components like `toggle`, `collapse`, and `modal` use CSS tricks
> (checkbox hack, `:checked` selectors) that daisyUI handles for you. Factor this in.

---

## Summary table

| daisyUI feature | Replaceable with bare Tailwind? | Effort |
|---|---|---|
| Color tokens / theme | ✅ Yes, trivially | Minutes |
| Light + dark theme switching | ✅ Yes — `@theme` + `.dark {}` override + one JS line | Low |
| `btn`, `badge`, `alert`, `card` | ✅ Yes — own `@layer components` | Low–Medium |
| `input`, `select`, `textarea` | ✅ Yes | Low |
| `toggle`, `checkbox`, `radio` | ⚠️ Yes but fiddly | Medium |
| `modal`, `drawer`, `dropdown` | ❌ Not without JS | High |
| `collapse`, `tab` (CSS-only) | ⚠️ Possible | Medium |

## Option decision flowchart

```
Does the codebase use daisyUI component class names (btn, badge, modal...)?
│
├── NO, or very few
│   └── Is light + dark theme switching needed?
│       ├── YES → Option D ⭐ (own tokens + own components, full control)
│       └── NO  → Option B  (tokens only, no components layer needed yet)
│
└── YES, many classes used
    └── Are you willing to rewrite them over time?
        ├── YES → Option C (keep theme plugin now, migrate gradually)
        └── NO  → Option A (keep daisyUI as-is, no changes)
```
