// src/features/evaluations/components/AnnotationForm.tsx
import { useState } from 'react'
import React from 'react'
import { useAddAnnotation } from '../hooks'
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
  annotations: Annotation[]
}

export function AnnotationForm({ evalId, annotations }: Props) {
  const addAnnotation = useAddAnnotation(evalId)
  const [showForm, setShowForm] = useState(false)
  const [content, setContent] = useState('')
  const [author, setAuthor] = useState('')
  const [category, setCategory] = useState('')

  function handleSave() {
    addAnnotation.mutate(
      { content, author: author || undefined, category: category || undefined },
      {
        onSuccess: () => {
          setContent(''); setAuthor(''); setCategory(''); setShowForm(false)
        },
      }
    )
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wide">
          Notes{annotations.length > 0 && (
            <span className="text-slate-600 normal-case font-normal ml-1">({annotations.length})</span>
          )}
        </h2>
        <button
          onClick={() => setShowForm(v => !v)}
          className="px-2.5 py-1 text-xs font-medium rounded border border-slate-600 text-slate-300 hover:border-slate-400 hover:text-slate-100 transition-colors"
        >
          {showForm ? 'Cancel' : '+ Add note'}
        </button>
      </div>

      {showForm && (
        <div className="bg-[#111827] border border-slate-700 rounded-xl p-4 space-y-3">
          <textarea
            value={content}
            onChange={e => setContent(e.target.value)}
            placeholder="Note content…"
            rows={3}
            className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500 resize-none"
          />
          <div className="grid grid-cols-2 gap-2">
            <input
              value={author}
              onChange={e => setAuthor(e.target.value)}
              placeholder="Author"
              className="px-3 py-2 bg-slate-800 border border-slate-600 rounded text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
            <input
              value={category}
              onChange={e => setCategory(e.target.value)}
              placeholder="Category (e.g. investigation)"
              className="px-3 py-2 bg-slate-800 border border-slate-600 rounded text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
          </div>
          <div className="flex justify-end">
            <button
              onClick={handleSave}
              disabled={!content.trim() || addAnnotation.isPending}
              className="px-3 py-1.5 text-xs font-medium rounded bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {addAnnotation.isPending ? 'Saving…' : 'Save note'}
            </button>
          </div>
        </div>
      )}

      {annotations.map(a => (
        <div key={a.id} className="bg-amber-950/30 border border-amber-700/40 rounded-lg p-3 text-sm flex gap-3">
          <span className="text-amber-400 text-lg leading-none">⚑</span>
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-0.5 flex-wrap">
              {a.category && (
                <span className="text-xs bg-amber-900/40 text-amber-300 px-1.5 py-0.5 rounded">{a.category}</span>
              )}
              {a.author && <span className="text-slate-400 text-xs">{a.author}</span>}
              <span className="text-slate-600 text-xs ml-auto">{a.created_at.slice(0, 16).replace('T', ' ')}</span>
            </div>
            {a.content && <p className="text-slate-300"><LinkifiedText text={a.content} /></p>}
          </div>
        </div>
      ))}

      {annotations.length === 0 && !showForm && (
        <p className="text-xs text-slate-600">No notes yet.</p>
      )}
    </div>
  )
}
