# Notes Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the notes UI so the form matches note entries (amber palette), the section is always visible, supports compact/expanded views, provides quick-add from the header, and heatmaps show context-appropriate note indicators.

**Architecture:** The AnnotationForm component gets split into three focused files: a section shell with header/toggle, a form card, and a note entry renderer. The EvaluationActions dropdown gains "Add Note" as its first item. The heatmap note indicator changes from white triangles to amber squares (group view) or chat-alert icons above columns (eval detail view via a new `NoteIndicatorRow` rendered above `HeatmapChart`).

**Tech Stack:** React 18, TypeScript, Tailwind CSS v4, lucide-react (`MessageSquareWarning`), ECharts (custom renderItem)

---

## File Structure

| Action | Path | Responsibility |
|--------|------|----------------|
| Rewrite | `ui/src/features/evaluations/components/AnnotationForm.tsx` | Section shell: always-visible header row, compact/expanded toggle, form visibility, note list |
| Extract | `ui/src/features/evaluations/components/NoteEntry.tsx` | Single note renderer (compact + expanded variants), `LinkifiedText` helper |
| Extract | `ui/src/features/evaluations/components/AddNoteForm.tsx` | Amber-palette add-note card (accent strip + single-line input + author/category) |
| Modify | `ui/src/features/evaluations/components/EvaluationActions.tsx:68-146` | Add "Add Note" as first dropdown item with amber accent + separator |
| Modify | `ui/src/features/evaluations/components/EvaluationHeader.tsx:11-23,42-77` | Accept `noteButton` prop, render next to actions slot |
| Modify | `ui/src/pages/EvaluationDetailPage.tsx:10,71-138,155` | Wire `onAddNote` to scroll+open form, pass noteButton prop to header |
| Modify | `ui/src/features/navigator/components/AssetPanel.tsx:11-12,122-154,171-174` | Same wiring as EvaluationDetailPage |
| Modify | `ui/src/components/charts/HeatmapChart.tsx:196-209` | Change white triangle → amber square for note indicator |
| Create | `ui/src/components/charts/NoteIndicatorRow.tsx` | Row of chat-alert icons above heatmap columns that have notes |
| Modify | `ui/src/features/navigator/components/AssetHeatmap.tsx:49-59` | Render `NoteIndicatorRow` above HeatmapChart for eval-detail context |
| Modify | `ui/src/features/navigator/utils.ts` | Pass `hasNote` through to AssetHeatmap cells |

---

### Task 1: Extract `NoteEntry` component

**Files:**
- Create: `ui/src/features/evaluations/components/NoteEntry.tsx`
- Modify: `ui/src/features/evaluations/components/AnnotationForm.tsx`

- [ ] **Step 1: Create `NoteEntry.tsx` with compact and expanded variants**

```tsx
// ui/src/features/evaluations/components/NoteEntry.tsx
import React from 'react'
import type { Annotation } from '../types'

const URL_RE = /https?:\/\/[^\s]+/g

function LinkifiedText({ text }: { text: string }) {
  const parts: React.ReactNode[] = []
  let last = 0
  for (const m of text.matchAll(URL_RE)) {
    if (m.index! > last) parts.push(text.slice(last, m.index))
    parts.push(
      <a key={m.index} href={m[0]} target="_blank" rel="noopener noreferrer"
        className="text-indigo-400 hover:text-indigo-300 hover:underline break-all">
        {m[0]}
      </a>
    )
    last = m.index! + m[0].length
  }
  if (last < text.length) parts.push(text.slice(last))
  return <>{parts}</>
}

interface Props {
  annotation: Annotation
  compact?: boolean
}

export function NoteEntry({ annotation: a, compact }: Props) {
  if (compact) {
    return (
      <div className="bg-amber-950/15 border border-amber-700/20 rounded px-3 py-1.5 text-sm flex items-center gap-2">
        <span className="text-amber-400 text-xs leading-none">⚑</span>
        {a.category && (
          <span className="text-[10px] bg-amber-900/40 text-amber-300 px-1.5 py-0.5 rounded shrink-0">{a.category}</span>
        )}
        <span className="text-foreground/70 text-xs truncate flex-1">{a.content}</span>
        <span className="text-muted-foreground text-[10px] shrink-0 ml-auto">
          {a.created_at.slice(5, 16).replace('T', ' ')}
        </span>
      </div>
    )
  }

  return (
    <div className="bg-amber-950/20 border border-amber-700/30 rounded-md px-3 py-2 text-sm">
      {/* Row 1: flag + category + content inline */}
      <div className="flex items-start gap-2">
        <span className="text-amber-400 text-sm leading-none mt-0.5">⚑</span>
        {a.category && (
          <span className="text-[10px] bg-amber-900/40 text-amber-300 px-1.5 py-0.5 rounded shrink-0">{a.category}</span>
        )}
        <span className="text-foreground/85 text-xs flex-1">
          {a.content && <LinkifiedText text={a.content} />}
        </span>
      </div>
      {/* Row 2: author + meta + date */}
      <div className="flex items-center gap-2 mt-1 ml-5">
        {a.author && <span className="text-muted-foreground text-[10px]">{a.author}</span>}
        {a.meta && Object.keys(a.meta).length > 0 && (
          <span className="text-muted-foreground text-[10px]">
            {Object.entries(a.meta).map(([k, v]) => `${k}: ${v}`).join(' · ')}
          </span>
        )}
        <span className="text-muted-foreground/60 text-[10px] ml-auto">
          {a.created_at.slice(0, 16).replace('T', ' ')}
        </span>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify the file compiles**

Run: `npx tsc --noEmit --pretty 2>&1 | head -20` from `ui/`
Expected: No errors in NoteEntry.tsx

- [ ] **Step 3: Commit**

```
git add ui/src/features/evaluations/components/NoteEntry.tsx
git commit -m "feat(ui): extract NoteEntry with compact and expanded variants"
```

---

### Task 2: Extract `AddNoteForm` component (amber palette)

**Files:**
- Create: `ui/src/features/evaluations/components/AddNoteForm.tsx`

- [ ] **Step 1: Create `AddNoteForm.tsx`**

```tsx
// ui/src/features/evaluations/components/AddNoteForm.tsx
import { useState } from 'react'
import { useAddAnnotation } from '../hooks'

interface Props {
  evalId: string
  onClose: () => void
}

export function AddNoteForm({ evalId, onClose }: Props) {
  const addAnnotation = useAddAnnotation(evalId)
  const [content, setContent] = useState('')
  const [author, setAuthor] = useState('')
  const [category, setCategory] = useState('')

  function handleSave() {
    if (!content.trim()) return
    addAnnotation.mutate(
      { content, author: author || undefined, category: category || undefined },
      { onSuccess: () => { setContent(''); setAuthor(''); setCategory(''); onClose() } },
    )
  }

  return (
    <div className="flex justify-end">
      <div className="w-full max-w-md border border-amber-700/40 rounded-xl bg-popover overflow-hidden">
        {/* Amber accent strip */}
        <div className="h-[3px] bg-amber-500" />
        <div className="p-4 space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium text-amber-400"
              style={{ fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif" }}>
              Add Note
            </p>
            <button onClick={onClose}
              className="text-xs text-muted-foreground hover:text-foreground transition-colors">
              Cancel
            </button>
          </div>

          <input
            value={content}
            onChange={e => setContent(e.target.value)}
            placeholder="Note content…"
            className="w-full px-3 py-2 bg-background border border-border rounded-md text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-amber-500"
          />

          <div className="grid grid-cols-2 gap-2">
            <input
              value={author}
              onChange={e => setAuthor(e.target.value)}
              placeholder="Author"
              className="px-3 py-2 bg-background border border-border rounded-md text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-amber-500"
            />
            <input
              value={category}
              onChange={e => setCategory(e.target.value)}
              placeholder="Category"
              className="px-3 py-2 bg-background border border-border rounded-md text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-amber-500"
            />
          </div>

          <div className="flex justify-end">
            <button
              onClick={handleSave}
              disabled={!content.trim() || addAnnotation.isPending}
              className="px-3 py-1.5 text-xs font-medium rounded-md bg-amber-500 text-black hover:bg-amber-400 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {addAnnotation.isPending ? 'Saving…' : 'Save note'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify the file compiles**

Run: `npx tsc --noEmit --pretty 2>&1 | head -20` from `ui/`
Expected: No errors in AddNoteForm.tsx

- [ ] **Step 3: Commit**

```
git add ui/src/features/evaluations/components/AddNoteForm.tsx
git commit -m "feat(ui): add AddNoteForm with amber palette, compact right-aligned card"
```

---

### Task 3: Rewrite `AnnotationForm` as notes section shell

**Files:**
- Rewrite: `ui/src/features/evaluations/components/AnnotationForm.tsx`

The section is **always visible** (even with 0 notes). Header shows count, compact/expanded toggle, and `+ Note` button. The form opens below the header when triggered.

- [ ] **Step 1: Rewrite `AnnotationForm.tsx`**

```tsx
// ui/src/features/evaluations/components/AnnotationForm.tsx
import { useState, useImperativeHandle, forwardRef } from 'react'
import type { Annotation } from '../types'
import { NoteEntry } from './NoteEntry'
import { AddNoteForm } from './AddNoteForm'

export interface AnnotationSectionHandle {
  openForm: () => void
}

interface Props {
  evalId: string
  annotations: Annotation[]
}

export const AnnotationSection = forwardRef<AnnotationSectionHandle, Props>(
  function AnnotationSection({ evalId, annotations }, ref) {
    const [showForm, setShowForm] = useState(false)
    const [viewMode, setViewMode] = useState<'compact' | 'expanded'>('expanded')

    useImperativeHandle(ref, () => ({
      openForm: () => setShowForm(true),
    }))

    return (
      <div className="space-y-2">
        {/* Header row — always visible */}
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide"
            style={{ fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif" }}>
            Notes
            <span className="normal-case font-normal ml-1 text-muted-foreground/60">
              ({annotations.length})
            </span>
          </h2>

          <div className="flex items-center gap-3">
            {/* View mode toggle */}
            {annotations.length > 0 && (
              <div className="flex items-center gap-1 text-[10px]"
                style={{ fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif" }}>
                <button
                  onClick={() => setViewMode('compact')}
                  className={viewMode === 'compact' ? 'text-amber-400 font-semibold' : 'text-muted-foreground/50 hover:text-muted-foreground'}
                >
                  compact
                </button>
                <span className="text-muted-foreground/30">/</span>
                <button
                  onClick={() => setViewMode('expanded')}
                  className={viewMode === 'expanded' ? 'text-amber-400 font-semibold' : 'text-muted-foreground/50 hover:text-muted-foreground'}
                >
                  expanded
                </button>
              </div>
            )}

            {/* + Note button */}
            <button
              onClick={() => setShowForm(v => !v)}
              className="px-2 py-1 text-[10px] font-medium rounded border border-amber-700/50 text-amber-400 hover:border-amber-500 hover:text-amber-300 transition-colors"
              style={{ fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif" }}
            >
              {showForm ? 'Cancel' : '+ Note'}
            </button>
          </div>
        </div>

        {/* Add note form */}
        {showForm && (
          <AddNoteForm evalId={evalId} onClose={() => setShowForm(false)} />
        )}

        {/* Note entries */}
        {annotations.map(a => (
          <NoteEntry key={a.id} annotation={a} compact={viewMode === 'compact'} />
        ))}

        {annotations.length === 0 && !showForm && (
          <p className="text-xs text-muted-foreground/40">No notes yet.</p>
        )}
      </div>
    )
  }
)

// Re-export for backwards compatibility during transition
export { AnnotationSection as AnnotationForm }
```

- [ ] **Step 2: Verify the file compiles and existing imports work**

Run: `npx tsc --noEmit --pretty 2>&1 | head -30` from `ui/`
Expected: No errors — `AnnotationForm` export still works for `EvaluationDetailPage` and `AssetPanel`

- [ ] **Step 3: Commit**

```
git add ui/src/features/evaluations/components/AnnotationForm.tsx
git commit -m "feat(ui): rewrite AnnotationForm as always-visible section with compact/expanded toggle"
```

---

### Task 4: Add note icon button to header + "Add Note" in Actions dropdown

**Files:**
- Modify: `ui/src/features/evaluations/components/EvaluationHeader.tsx`
- Modify: `ui/src/features/evaluations/components/EvaluationActions.tsx`

- [ ] **Step 1: Add `noteButton` prop to EvaluationHeader**

In `ui/src/features/evaluations/components/EvaluationHeader.tsx`, add `noteButton?: ReactNode` to the `Props` interface and render it in the right column before `actions`:

```tsx
interface Props {
  // ... existing props
  /** Note icon button — rendered left of actions */
  noteButton?: ReactNode
  actions?: ReactNode
}
```

In the right column JSX (line 74), replace the existing div:

Old (line 74-76):
```tsx
<div className="flex flex-col items-end gap-2">
  {actions}
</div>
```

New:
```tsx
<div className="flex items-center gap-2 justify-end">
  {noteButton}
  {actions}
</div>
```

This changes `flex-col items-end` → `items-center justify-end` for horizontal layout, and adds `{noteButton}` before `{actions}`.

- [ ] **Step 2: Add "Add Note" as first item in EvaluationActionsButton dropdown**

In `ui/src/features/evaluations/components/EvaluationActions.tsx`:

1. Add to the imports: `import { MoreVertical, MessageSquareWarning } from 'lucide-react'`

2. Add `onAddNote?: () => void` to the `ButtonProps` interface.

3. In the dropdown menu (inside the `{menuOpen && ...}` block), add an "Add Note" button at the top before the action items, with a separator below:

```tsx
{menuOpen && (
  <div className="absolute right-0 top-full mt-1 z-20 min-w-[280px] bg-popover border border-border rounded-xl shadow-xl overflow-hidden py-2">
    {/* Add Note — first item */}
    {onAddNote && (
      <>
        <button
          onClick={() => { onAddNote(); setMenuOpen(false) }}
          className="flex items-start gap-3 w-full text-left px-3 py-2.5 transition-colors hover:bg-amber-500/10 group"
        >
          <div
            className="w-[3px] rounded-full shrink-0 mt-0.5"
            style={{ backgroundColor: '#F59E0B', height: 36 }}
          />
          <div className="min-w-0">
            <div className="text-[13px] font-medium text-amber-400">Add Note</div>
            <div className="text-[11px] text-muted-foreground mt-0.5">Annotate this evaluation</div>
          </div>
        </button>
        <div className="mx-3 my-1 border-t border-border" />
      </>
    )}
    {actions.map(action => (
      /* ... existing action items unchanged ... */
    ))}
  </div>
)}
```

4. Also export a standalone note icon button component from the same file:

```tsx
export function NoteIconButton({ onClick, annotationCount }: { onClick: () => void; annotationCount: number }) {
  return (
    <button
      onClick={onClick}
      className="relative p-2 rounded-lg border border-amber-700/40 text-amber-400 hover:bg-amber-500/10 hover:border-amber-500/50 transition-colors"
      title="Add note"
    >
      <MessageSquareWarning className="w-4 h-4" />
      {annotationCount > 0 && (
        <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-amber-500 text-[9px] font-bold text-black flex items-center justify-center">
          {annotationCount > 9 ? '9+' : annotationCount}
        </span>
      )}
    </button>
  )
}
```

- [ ] **Step 3: Verify both files compile**

Run: `npx tsc --noEmit --pretty 2>&1 | head -30` from `ui/`
Expected: No errors

- [ ] **Step 4: Commit**

```
git add ui/src/features/evaluations/components/EvaluationHeader.tsx ui/src/features/evaluations/components/EvaluationActions.tsx
git commit -m "feat(ui): add note icon button to header and 'Add Note' as first Actions dropdown item"
```

---

### Task 5: Wire `EvaluationDetailPage` to new notes components

**Files:**
- Modify: `ui/src/pages/EvaluationDetailPage.tsx`

- [ ] **Step 1: Update imports and add ref + scroll wiring**

Replace the `AnnotationForm` import and add ref handling:

```tsx
import { useRef } from 'react'  // add to existing import
import { AnnotationSection, type AnnotationSectionHandle } from '@/features/evaluations/components/AnnotationForm'
import { EvaluationActionsButton, EvaluationActionForm, NoteIconButton, type ActionKind } from '@/features/evaluations/components/EvaluationActions'
```

Inside the component, add a ref:

```tsx
const notesRef = useRef<AnnotationSectionHandle>(null)

function handleAddNote() {
  notesRef.current?.openForm()
  document.getElementById('notes-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
```

- [ ] **Step 2: Pass `noteButton` and `onAddNote` to header/actions**

Update the `EvaluationHeader` usage to include `noteButton`:

```tsx
<EvaluationHeader
  // ... existing props
  noteButton={
    !ev.invalidated ? (
      <NoteIconButton onClick={handleAddNote} annotationCount={ev.annotations.length} />
    ) : undefined
  }
  actions={
    <EvaluationActionsButton
      currentResult={ev.result}
      invalidated={ev.invalidated}
      activeAction={activeAction}
      onSelectAction={setActiveAction}
      onAddNote={handleAddNote}
    />
  }
/>
```

- [ ] **Step 3: Update notes section rendering**

Replace the old `AnnotationForm` with:

```tsx
{/* Notes — always visible */}
<div id="notes-section">
  <AnnotationSection ref={notesRef} evalId={id!} annotations={ev.annotations} />
</div>
```

- [ ] **Step 4: Verify the page compiles**

Run: `npx tsc --noEmit --pretty 2>&1 | head -30` from `ui/`
Expected: No errors

- [ ] **Step 5: Commit**

```
git add ui/src/pages/EvaluationDetailPage.tsx
git commit -m "feat(ui): wire EvaluationDetailPage to new notes section with quick-add from header"
```

---

### Task 6: Wire `AssetPanel` to new notes components

**Files:**
- Modify: `ui/src/features/navigator/components/AssetPanel.tsx`

- [ ] **Step 1: Update imports**

Replace the `AnnotationForm` import and add new imports at the top of `AssetPanel.tsx`:

```tsx
import { useRef } from 'react'  // add to existing useState, useMemo import
import { AnnotationSection, type AnnotationSectionHandle } from '@/features/evaluations/components/AnnotationForm'
import { EvaluationActionsButton, EvaluationActionForm, NoteIconButton, type ActionKind } from '@/features/evaluations/components/EvaluationActions'
```

Remove the old import:
```tsx
// DELETE: import { AnnotationForm } from '@/features/evaluations/components/AnnotationForm'
```

- [ ] **Step 2: Add ref and handler inside the component**

After the existing `const [metricGroupFilter, ...]` state, add:

```tsx
const notesRef = useRef<AnnotationSectionHandle>(null)

function handleAddNote() {
  notesRef.current?.openForm()
  document.getElementById('notes-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
```

- [ ] **Step 3: Pass `noteButton` to `EvaluationHeader`**

Update the `EvaluationHeader` usage (around line 123) to add `noteButton`:

```tsx
<EvaluationHeader
  title={assetName}
  titleMono
  result={displayResult}
  score={score}
  metadata={ev ? (/* ... existing metadata JSX unchanged ... */) : undefined}
  noteButton={effectiveEvalId && ev && !ev.invalidated ? (
    <NoteIconButton onClick={handleAddNote} annotationCount={(ev.annotations ?? []).length} />
  ) : undefined}
  actions={effectiveEvalId && ev ? (
    <EvaluationActionsButton
      currentResult={ev.result}
      invalidated={ev.invalidated}
      activeAction={activeAction}
      onSelectAction={setActiveAction}
      onAddNote={handleAddNote}
    />
  ) : undefined}
/>
```

- [ ] **Step 4: Replace `<AnnotationForm>` with `<AnnotationSection>`**

Replace the old notes block (around line 172-174):

Old:
```tsx
{!isLoading && effectiveEvalId && ev && (
  <AnnotationForm evalId={effectiveEvalId} annotations={ev.annotations ?? []} />
)}
```

New:
```tsx
{!isLoading && effectiveEvalId && ev && (
  <div id="notes-section">
    <AnnotationSection ref={notesRef} evalId={effectiveEvalId} annotations={ev.annotations ?? []} />
  </div>
)}

- [ ] **Step 2: Verify**

Run: `npx tsc --noEmit --pretty 2>&1 | head -30` from `ui/`
Expected: No errors

- [ ] **Step 3: Commit**

```
git add ui/src/features/navigator/components/AssetPanel.tsx
git commit -m "feat(ui): wire AssetPanel to new notes section with quick-add from header"
```

---

### Task 7: Heatmap — amber squares for group view

**Files:**
- Modify: `ui/src/components/charts/HeatmapChart.tsx:196-209`

- [ ] **Step 1: Change white triangle to amber square**

In `HeatmapChart.tsx`, find the annotation indicator code (lines 196-209) and replace the white polygon triangle with an amber rectangle in the top-right corner:

```tsx
if (annotations && cellData?.hasNote) {
  const s = Math.min(6, rw / 3, rh / 3)
  children.push({
    type: 'rect',
    shape: {
      x: rx + rw - s,
      y: ry,
      width: s,
      height: s,
    },
    style: { fill: '#F59E0B' },  // amber-500
  })
}
```

- [ ] **Step 2: Verify chart still renders**

Run: `npx tsc --noEmit --pretty 2>&1 | head -20` from `ui/`
Expected: No errors

- [ ] **Step 3: Commit**

```
git add ui/src/components/charts/HeatmapChart.tsx
git commit -m "feat(ui): change heatmap note indicator from white triangle to amber square"
```

---

### Task 8: Heatmap — chat-alert icon row for eval detail (AssetHeatmap)

**Files:**
- Create: `ui/src/components/charts/NoteIndicatorRow.tsx`
- Modify: `ui/src/features/navigator/components/AssetHeatmap.tsx`
- Modify: `ui/src/features/navigator/utils.ts` (if `hasNote` isn't already passed through)

The eval detail's `AssetHeatmap` shows metrics as rows, days as columns. Notes are per-evaluation (per-column), not per-indicator (per-row). Instead of per-cell squares, we render a row of amber chat-alert icons above the chart for columns that have notes.

- [ ] **Step 1: Check if `hasNote` is available on AssetHeatmap cells**

Read `ui/src/features/navigator/utils.ts` to see if `buildAssetHeatmapData` passes `hasNote` through. If not, we need to add it from the `MetricHeatmapResponse` data.

Currently `MetricHeatmapCell` (in `types.ts`) does NOT have `hasNote`. The note data comes from the evaluation, not individual metrics. We need to determine which columns (slots) have notes by checking the evaluation summaries.

**Approach:** The `AssetHeatmap` component doesn't have access to evaluation-level note data. Instead, we'll pass a `notedSlots` set from `AssetPanel` (which has access to evaluation summaries) into `AssetHeatmap`.

- [ ] **Step 2: Create `NoteIndicatorRow.tsx`**

```tsx
// ui/src/components/charts/NoteIndicatorRow.tsx
import { MessageSquareWarning } from 'lucide-react'

interface Props {
  /** Ordered list of column keys (same as HeatmapChart columns) */
  columns: string[]
  /** Set of column keys that have notes */
  notedColumns: Set<string>
  /** Called when user clicks an indicator */
  onIndicatorClick?: (slot: string) => void
}

export function NoteIndicatorRow({ columns, notedColumns, onIndicatorClick }: Props) {
  if (notedColumns.size === 0) return null

  return (
    <div className="flex items-center" style={{ paddingLeft: 210, paddingRight: 20 }}>
      {columns.map(col => (
        <div key={col} className="flex-1 flex justify-center">
          {notedColumns.has(col) ? (
            <button
              onClick={() => onIndicatorClick?.(col)}
              className="text-amber-400 hover:text-amber-300 transition-colors"
              title="This evaluation has notes"
            >
              <MessageSquareWarning className="w-3.5 h-3.5" />
            </button>
          ) : (
            <span className="w-3.5 h-3.5" />
          )}
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 3: Update `AssetHeatmap` to accept `notedSlots` and render `NoteIndicatorRow`**

In `ui/src/features/navigator/components/AssetHeatmap.tsx`:

Add `notedSlots?: Set<string>` to Props, import `NoteIndicatorRow`, render it above the `HeatmapChart`:

```tsx
import { NoteIndicatorRow } from '@/components/charts/NoteIndicatorRow'

interface Props {
  data: MetricHeatmapResponse
  selectedEvalId?: string
  onEvalSelect?: (evalId: string) => void
  /** Slots (ISO timestamps) that have evaluation-level notes */
  notedSlots?: Set<string>
}

// ... in the return:
return (
  <>
    {notedSlots && notedSlots.size > 0 && (
      <NoteIndicatorRow
        columns={slots}
        notedColumns={notedSlots}
      />
    )}
    <HeatmapChart
      rows={rows}
      columns={slots}
      cells={cells}
      selectedColumn={selectedColumn}
      onCellClick={onCellClick}
      formatTooltip={formatTooltip}
      instructionText="Click a cell to select that evaluation."
    />
  </>
)
```

Note: Do NOT pass `annotations={true}` here — no per-cell indicators in eval detail.

- [ ] **Step 4: Compute `notedSlots` in `AssetPanel` and pass to `AssetHeatmap`**

In `ui/src/features/navigator/components/AssetPanel.tsx`, compute the set from evaluation summaries:

The heatmap API's `slots` and the evaluation summaries' `period_start` values are the same ISO timestamps, so we can match directly. However, to be robust, we cross-reference via `eval_id` from heatmap cells:

```tsx
const notedSlots = useMemo(() => {
  if (!heatmapData) return new Set<string>()
  // Build a set of eval IDs that have notes
  const notedIds = new Set(
    evals.filter(e => (e.annotation_count ?? 0) > 0).map(e => e.id),
  )
  // Find which heatmap slots contain those eval IDs
  const slots = new Set<string>()
  for (const c of heatmapData.cells) {
    if (c.eval_id && notedIds.has(c.eval_id)) {
      slots.add(c.slot)
    }
  }
  return slots
}, [evals, heatmapData])
```

Pass to `AssetHeatmap`:

```tsx
<AssetHeatmap
  data={heatmapData}
  selectedEvalId={effectiveEvalId}
  onEvalSelect={setSelectedEvalId}
  notedSlots={notedSlots}
/>
```

- [ ] **Step 5: Verify everything compiles**

Run: `npx tsc --noEmit --pretty 2>&1 | head -30` from `ui/`
Expected: No errors

- [ ] **Step 6: Commit**

```
git add ui/src/components/charts/NoteIndicatorRow.tsx ui/src/features/navigator/components/AssetHeatmap.tsx ui/src/features/navigator/components/AssetPanel.tsx
git commit -m "feat(ui): add chat-alert icon row above AssetHeatmap for eval-detail note indicators"
```

---

### Task 9: Visual verification

- [ ] **Step 1: Start the dev server**

Run: `npx vite --host` from `ui/`

- [ ] **Step 2: Verify each feature visually**

1. **Notes section always visible** — Navigate to any evaluation detail page. The "NOTES (N)" header should be visible even with 0 notes.
2. **Compact/expanded toggle** — If notes exist, toggle between compact (single-line) and expanded (2-row) views.
3. **Add note form** — Click "+ Note" button. Form should appear with amber accent strip, amber save button, neutral background (no tinted bg).
4. **Note icon in header** — Amber chat-alert icon button should appear left of the green Actions button. Badge shows note count.
5. **Add Note in Actions dropdown** — Click Actions. "Add Note" should be the first item with amber accent, followed by a separator.
6. **Quick-add wiring** — Clicking the note icon or "Add Note" dropdown item should scroll to notes section and open the form.
7. **Group heatmap** — Navigate to a group in Navigator. Cells with notes should show amber corner square (not white triangle).
8. **Eval detail heatmap** — Navigate to an asset in Navigator. Chat-alert icons should appear above columns that have notes. No per-cell squares.
9. **AssetPanel** — Same note icon + section + toggle should work in the navigator's asset panel view.
