// ui/src/features/slos/components/SloList.tsx
import { useState } from 'react'
import { useSloDetail, useDeleteSlo } from '@/features/slos/hooks'
import type { Slo } from '@/features/slos'
import { SloObjectiveTable } from './SloObjectiveTable'
import { SloObjectiveEditor } from './SloObjectiveEditor'
import { SloHistoryPanel } from './SloHistoryPanel'

type Mode = 'view' | 'edit-rows' | 'history'

function TabBtn({ active, onClick, children }: {
  active: boolean; onClick: () => void; children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 text-xs font-medium rounded transition-colors border ${
        active
          ? 'bg-primary/20 border-primary/50 text-link'
          : 'bg-transparent border-border text-muted-foreground hover:border-border hover:text-foreground'
      }`}
    >
      {children}
    </button>
  )
}

function SloDetail({ name }: { name: string }) {
  const { data: slo, isLoading, isError } = useSloDetail(name)
  const [mode, setMode] = useState<Mode>('view')

  if (isLoading) return <p className="text-muted-foreground text-sm py-3">Loading\u2026</p>
  if (isError || !slo) return <p className="text-destructive-form-text text-sm py-3">Failed to load.</p>

  return (
    <div className="border-t border-border mt-3 pt-4 space-y-4">
      <div className="flex gap-2 flex-wrap">
        <TabBtn active={mode === 'view'} onClick={() => setMode('view')}>View</TabBtn>
        <TabBtn active={mode === 'edit-rows'} onClick={() => setMode('edit-rows')}>Edit Rows</TabBtn>
        <TabBtn active={mode === 'history'} onClick={() => setMode('history')}>History</TabBtn>
        <button
          disabled
          title="Coming soon"
          className="px-3 py-1.5 text-xs font-medium rounded border border-border text-muted-foreground/60 cursor-not-allowed"
        >
          Test SLO
        </button>
      </div>

      {mode === 'view' && <SloObjectiveTable slo={slo} />}
      {mode === 'edit-rows' && (
        <SloObjectiveEditor slo={slo} onCancel={() => setMode('view')} onSaved={() => setMode('view')} />
      )}
      {mode === 'history' && <SloHistoryPanel name={name} />}
    </div>
  )
}

function DeleteConfirm({ name, onDone }: { name: string; onDone: () => void }) {
  const del = useDeleteSlo()

  return (
    <div className="flex items-center gap-2 bg-destructive-form-bg border border-destructive-form-border rounded-lg px-3 py-2">
      <span className="text-xs text-destructive-form-text">Deactivate <strong>{name}</strong>? All versions will be marked inactive.</span>
      <button
        onClick={() => del.mutate(name, { onSuccess: onDone })}
        disabled={del.isPending}
        className="px-2.5 py-1 text-xs font-medium rounded bg-action-destructive-confirm text-white hover:bg-action-destructive-confirm/80 disabled:opacity-40 transition-colors shrink-0"
      >
        {del.isPending ? 'Deactivating\u2026' : 'Confirm'}
      </button>
      <button
        onClick={onDone}
        className="px-2.5 py-1 text-xs rounded border border-border text-muted-foreground hover:text-foreground transition-colors shrink-0"
      >
        Cancel
      </button>
    </div>
  )
}

interface Props {
  slos: Slo[]
  selectedGroup: string | null
  showAll: boolean
  onShowAll: () => void
  onLinkSlo: (sloName: string) => void
}

export function SloList({ slos, selectedGroup, showAll, onShowAll, onLinkSlo }: Props) {
  const [expandedSlo, setExpandedSlo] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)

  return (
    <div className="space-y-2">
      {slos.map(slo => {
        const tagEntries = Object.entries(slo.tags ?? {})
        const isExpanded = expandedSlo === slo.name
        const isConfirmingDelete = confirmDelete === slo.name

        return (
          <div
            key={slo.name}
            className={`bg-card border rounded-xl overflow-hidden transition-colors ${
              slo.active ? 'border-border' : 'border-border opacity-60'
            }`}
          >
            {/* Header row */}
            <div className="px-5 py-4 flex items-center gap-4">
              <button
                onClick={() => setExpandedSlo(prev => prev === slo.name ? null : slo.name)}
                className="text-muted-foreground text-xs w-3 shrink-0 hover:text-foreground transition-colors"
              >
                {isExpanded ? '\u25BC' : '\u25B6'}
              </button>

              <div
                className="flex items-center gap-2 min-w-0 flex-1 cursor-pointer"
                onClick={() => setExpandedSlo(prev => prev === slo.name ? null : slo.name)}
              >
                <span className="font-semibold text-foreground truncate">
                  {slo.displayName ?? slo.name}
                </span>
                <span className="text-xs text-muted-foreground shrink-0">v{slo.version}</span>
                {slo.active
                  ? <span className="text-xs bg-pass/20 text-pass border border-pass/30 px-1.5 py-0.5 rounded-full shrink-0">active</span>
                  : <span className="text-xs bg-surface-sunken/40 text-muted-foreground border border-border/40 px-1.5 py-0.5 rounded-full shrink-0">inactive</span>
                }
              </div>

              {tagEntries.length > 0 && (
                <div className="flex items-center gap-1 flex-wrap">
                  {tagEntries.map(([k, v]) => (
                    <span key={k} className="text-xs bg-surface-sunken/60 text-foreground px-1.5 py-0.5 rounded">
                      {k}: {v}
                    </span>
                  ))}
                </div>
              )}

              <div className="ml-auto flex items-center gap-4 text-xs text-muted-foreground shrink-0">
                {slo.author && <span>{slo.author}</span>}
                {slo.notes && (
                  <span className="max-w-xs truncate text-muted-foreground/60 italic" title={slo.notes}>
                    {slo.notes}
                  </span>
                )}
                <span className="text-muted-foreground/60">{slo.createdAt.toISOString().slice(0, 10)}</span>

                {slo.active && (
                  <button
                    onClick={e => { e.stopPropagation(); onLinkSlo(slo.name) }}
                    className="text-xs text-muted-foreground hover:text-primary transition-colors border border-transparent hover:border-primary/40 px-1.5 py-0.5 rounded"
                    title="Link to asset group"
                  >
                    + Group
                  </button>
                )}

                {slo.active && (
                  <button
                    onClick={e => { e.stopPropagation(); setConfirmDelete(slo.name) }}
                    className="text-xs text-muted-foreground/60 hover:text-action-destructive transition-colors border border-transparent hover:border-action-destructive/40 px-1.5 py-0.5 rounded"
                    title="Deactivate SLO"
                  >
                    Deactivate
                  </button>
                )}
              </div>
            </div>

            {isConfirmingDelete && (
              <div className="px-5 pb-3">
                <DeleteConfirm name={slo.name} onDone={() => setConfirmDelete(null)} />
              </div>
            )}

            {isExpanded && (
              <div className="px-5 pb-5">
                <SloDetail name={slo.name} />
              </div>
            )}
          </div>
        )
      })}

      {slos.length === 0 && selectedGroup && !showAll && (
        <div className="text-center py-8 text-muted-foreground text-sm">
          No SLOs linked to this group.{' '}
          <button
            onClick={onShowAll}
            className="text-primary hover:underline"
          >
            Show all SLOs
          </button>
        </div>
      )}
    </div>
  )
}
