// src/features/evaluations/components/EvaluationHeader.tsx
//
// Shared header card used by EvaluationDetailPage, AssetPanel, and GroupPanel.
// 3-column layout: left (title + badge + metadata) | center (score) | right (actions).

import type { ReactNode } from 'react'
import { ResultBadge } from './ResultBadge'
import { useTheme } from '@/lib/theme-context'
import { RESULT_COLOUR } from '@/lib/theme'

interface Props {
  title: string
  titleMono?: boolean
  subtitle?: string
  result?: string
  score?: number
  /** Color the score with the result color. False → foreground color. */
  scoreColored?: boolean
  /** SLO pass threshold — shown next to the score (e.g. "pass ≥90%") */
  passPct?: number | null
  /** SLO warning threshold — shown next to the score (e.g. "warn ≥75%") */
  warningPct?: number | null
  /** Metadata lines rendered below the title (asset info, SLO, etc.) */
  metadata?: ReactNode
  /** Toolbar rendered in right column, before noteButton/actions (e.g. time range picker) */
  toolbar?: ReactNode
  /** Note icon button rendered left of actions */
  noteButton?: ReactNode
  /** Right-column actions (invalidate button, etc.) */
  actions?: ReactNode
}

export function EvaluationHeader({
  title,
  titleMono,
  subtitle,
  result,
  score,
  scoreColored = true,
  passPct,
  warningPct,
  metadata,
  toolbar,
  noteButton,
  actions,
}: Props) {
  const { theme } = useTheme()
  const colours = RESULT_COLOUR[theme]

  const scoreColor = scoreColored && result
    ? colours[result as keyof typeof colours] ?? colours.error
    : undefined

  return (
    <div className="bg-[#111827] border border-slate-700 rounded-xl p-5 grid grid-cols-[1fr_auto_1fr] items-start gap-4">
      {/* Left — title + badge + metadata */}
      <div className="min-w-0">
        <div className="flex items-center gap-3 flex-wrap">
          <h1 className={`text-xl font-bold text-slate-100 ${titleMono ? 'font-mono' : ''}`}>
            {title}
          </h1>
          {result && <ResultBadge result={result} />}
        </div>
        {subtitle && (
          <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>
        )}
        {metadata && <div className="mt-2">{metadata}</div>}
      </div>

      {/* Center — score */}
      <div className="text-center pt-1">
        {score != null && (
          <>
            <div
              className="text-4xl font-bold tabular-nums"
              style={scoreColor ? { color: scoreColor } : undefined}
            >
              {score % 1 === 0 ? `${score}%` : `${score.toFixed(1)}%`}
            </div>
            {(passPct != null || warningPct != null) ? (
              <div className="flex items-center justify-center gap-3 text-[11px] mt-1">
                {passPct != null && (
                  <span className="text-pass">pass ≥{passPct}%</span>
                )}
                {warningPct != null && (
                  <span className="text-warning">warn ≥{warningPct}%</span>
                )}
              </div>
            ) : (
              <div className="text-xs text-slate-500 mt-0.5">total score</div>
            )}
          </>
        )}
      </div>

      {/* Right — toolbar + actions */}
      <div className="flex flex-col items-end gap-2">
        {toolbar}
        {(noteButton || actions) && (
          <div className="flex items-center gap-2">
            {noteButton}
            {actions}
          </div>
        )}
      </div>
    </div>
  )
}
