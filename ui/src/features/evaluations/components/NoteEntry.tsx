import { useState } from 'react'
import { DeletionConfirmForm } from '@/components/DeletionConfirmForm'
import { paletteOf } from '@/features/note-categories'
import { useHideAnnotation } from '../hooks'
import type { Annotation } from '../domain'

const URL_RE = /https?:\/\/[^\s]+/g

function LinkifiedText({ text }: { text: string }) {
  const parts: React.ReactNode[] = []
  let last = 0
  for (const m of text.matchAll(URL_RE)) {
    if (m.index! > last) parts.push(text.slice(last, m.index))
    parts.push(
      <a key={m.index} href={m[0]} target="_blank" rel="noopener noreferrer"
        className="text-link hover:text-link-hover hover:underline break-all">
        {m[0]}
      </a>
    )
    last = m.index! + m[0].length
  }
  if (last < text.length) parts.push(text.slice(last))
  return <>{parts}</>
}

interface CategoryAccentCardProps {
  palette: { bg: string; fg: string }
  variant: 'compact' | 'full'
  children: React.ReactNode
}

/** Neutral popover card with a coloured left accent bar. Shared between the
 * compact (single-line) and full (two-row) note layouts. */
function CategoryAccentCard({ palette, variant, children }: CategoryAccentCardProps) {
  const shape = variant === 'compact' ? 'rounded px-3 py-1.5' : 'rounded-md px-3 py-2'
  return (
    <div
      className={`bg-popover border border-border text-sm border-l-2 ${shape}`}
      style={{ borderLeftColor: palette.bg }}
    >
      {children}
    </div>
  )
}

function CategoryBadge({ label, palette }: { label: string; palette: { bg: string; fg: string } }) {
  return (
    <span
      className="text-[10px] px-1.5 py-0.5 rounded shrink-0"
      style={{ background: palette.bg, color: palette.fg }}
    >
      {label}
    </span>
  )
}

interface Props {
  runId: string
  annotation: Annotation
  compact?: boolean
}

export function NoteEntry({ runId, annotation: a, compact }: Props) {
  const hideAnnotation = useHideAnnotation(runId)
  const [hiding, setHiding] = useState(false)

  function handleHide(reason: string, author: string) {
    hideAnnotation.mutate(
      { annotationId: a.id, reason, author: author || undefined },
      { onSuccess: () => setHiding(false) },
    )
  }

  const palette = paletteOf(a.category.color)
  const deleteButton = (
    <button
      onClick={() => setHiding(true)}
      className="text-muted-foreground/40 hover:text-action-destructive text-xs transition-colors shrink-0"
      title="Delete note"
    >
      ✕
    </button>
  )

  if (compact && !hiding) {
    return (
      <CategoryAccentCard palette={palette} variant="compact">
        <div className="flex items-center gap-2">
          <span className="text-xs leading-none" style={{ color: palette.bg }}>⚑</span>
          <CategoryBadge label={a.category.label} palette={palette} />
          <span className="text-foreground/70 text-xs truncate flex-1">{a.content}</span>
          <span className="text-muted-foreground text-[10px] shrink-0 ml-auto">
            {a.createdAt.toISOString().slice(5, 16).replace('T', ' ')}
          </span>
          {deleteButton}
        </div>
      </CategoryAccentCard>
    )
  }

  return (
    <CategoryAccentCard palette={palette} variant="full">
      <div className="flex items-start gap-2">
        <span className="text-sm leading-none mt-0.5" style={{ color: palette.bg }}>⚑</span>
        <CategoryBadge label={a.category.label} palette={palette} />
        <span className="text-foreground/85 text-xs flex-1">
          {a.content && <LinkifiedText text={a.content} />}
        </span>
        {!hiding && deleteButton}
      </div>
      <div className="flex items-center gap-2 mt-1 ml-5">
        {a.author && <span className="text-muted-foreground text-[10px]">{a.author}</span>}
        {a.tags && Object.keys(a.tags).length > 0 && (
          <span className="text-muted-foreground text-[10px]">
            {Object.entries(a.tags).map(([k, v]) => `${k}: ${v}`).join(' · ')}
          </span>
        )}
        <span className="text-muted-foreground/60 text-[10px] ml-auto">
          {a.createdAt.toISOString().slice(0, 16).replace('T', ' ')}
        </span>
      </div>

      {hiding && (
        <div className="mt-2 ml-5">
          <DeletionConfirmForm
            title="Delete this note?"
            onConfirm={handleHide}
            onCancel={() => setHiding(false)}
            confirmLabel="Delete note"
            pendingLabel="Deleting\u2026"
            isPending={hideAnnotation.isPending}
            requireReason
            requireAuthor
          />
        </div>
      )}
    </CategoryAccentCard>
  )
}
