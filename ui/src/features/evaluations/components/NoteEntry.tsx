// ui/src/features/evaluations/components/NoteEntry.tsx
import { useState } from 'react'
import { useHideAnnotation } from '../hooks'
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
  evalId: string
  annotation: Annotation
  compact?: boolean
}

export function NoteEntry({ evalId, annotation: a, compact }: Props) {
  const hideAnnotation = useHideAnnotation(evalId)
  const [hiding, setHiding] = useState(false)
  const [hideReason, setHideReason] = useState('')
  const [hideAuthor, setHideAuthor] = useState('')

  function handleHide() {
    hideAnnotation.mutate(
      { annotationId: a.id, reason: hideReason, author: hideAuthor || undefined },
      { onSuccess: () => { setHiding(false); setHideReason(''); setHideAuthor('') } },
    )
  }

  if (compact && !hiding) {
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
        <button
          onClick={() => setHiding(true)}
          className="text-muted-foreground/40 hover:text-red-400 text-xs transition-colors shrink-0"
          title="Delete note"
        >
          ✕
        </button>
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
        {!hiding && (
          <button
            onClick={() => setHiding(true)}
            className="text-muted-foreground/40 hover:text-red-400 text-xs transition-colors shrink-0"
            title="Delete note"
          >
            ✕
          </button>
        )}
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

      {/* Hide/delete form */}
      {hiding && (
        <div className="mt-2 ml-5 border border-red-700/40 rounded-md bg-red-950/20 overflow-hidden">
          <div className="h-[3px] bg-red-500" />
          <div className="p-3 space-y-2">
            <p className="text-xs font-medium text-red-400"
              style={{ fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif" }}>
              Delete this note?
            </p>
            <input
              value={hideReason}
              onChange={e => setHideReason(e.target.value)}
              placeholder="Reason for deletion…"
              className="w-full px-3 py-1.5 bg-background border border-red-700/40 rounded-md text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-red-500"
            />
            <input
              value={hideAuthor}
              onChange={e => setHideAuthor(e.target.value)}
              placeholder="Your name"
              className="w-full px-3 py-1.5 bg-background border border-red-700/40 rounded-md text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-red-500"
            />
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setHiding(false)}
                className="px-3 py-1.5 text-xs font-medium rounded-md border border-border text-muted-foreground hover:border-muted-foreground/60 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleHide}
                disabled={!hideReason.trim() || hideAnnotation.isPending}
                className="px-3 py-1.5 text-xs font-medium rounded-md bg-red-600 text-white hover:bg-red-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                {hideAnnotation.isPending ? 'Deleting…' : 'Delete note'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
