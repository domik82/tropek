// src/pages/SloRegistryPage.tsx
import { useState, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useSlos, useSloDetail, useDeleteSlo, useGroupSloLinks } from '@/features/slos/hooks'
import { SloObjectiveTable } from '@/features/slos/components/SloObjectiveTable'
import { SloObjectiveEditor } from '@/features/slos/components/SloObjectiveEditor'
import { SloHistoryPanel } from '@/features/slos/components/SloHistoryPanel'
import { SloCreateForm } from '@/features/slos/components/SloCreateForm'
import { GroupSidebar } from '@/features/slos/components/GroupSidebar'
import { GroupCreateDialog } from '@/features/slos/components/GroupCreateDialog'
import { GroupEditDialog } from '@/features/slos/components/GroupEditDialog'
import { GroupDeleteDialog } from '@/features/slos/components/GroupDeleteDialog'
import { SloLinkDialog } from '@/features/slos/components/SloLinkDialog'

type Mode = 'view' | 'edit-rows' | 'history'

function TabBtn({ active, onClick, children }: {
  active: boolean; onClick: () => void; children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 text-xs font-medium rounded transition-colors border ${
        active
          ? 'bg-indigo-600/20 border-indigo-500/50 text-indigo-300'
          : 'bg-transparent border-slate-700 text-slate-400 hover:border-slate-500 hover:text-slate-200'
      }`}
    >
      {children}
    </button>
  )
}

function SloDetail({ name }: { name: string }) {
  const { data: slo, isLoading, isError } = useSloDetail(name)
  const [mode, setMode] = useState<Mode>('view')

  if (isLoading) return <p className="text-slate-500 text-sm py-3">Loading…</p>
  if (isError || !slo) return <p className="text-red-400 text-sm py-3">Failed to load.</p>

  return (
    <div className="border-t border-slate-800 mt-3 pt-4 space-y-4">
      <div className="flex gap-2 flex-wrap">
        <TabBtn active={mode === 'view'} onClick={() => setMode('view')}>View</TabBtn>
        <TabBtn active={mode === 'edit-rows'} onClick={() => setMode('edit-rows')}>Edit Rows</TabBtn>
        <TabBtn active={mode === 'history'} onClick={() => setMode('history')}>History</TabBtn>
        <button
          disabled
          title="Coming soon"
          className="px-3 py-1.5 text-xs font-medium rounded border border-slate-800 text-slate-600 cursor-not-allowed"
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

// ── Delete confirm inline ──────────────────────────────────────────────────────

function DeleteConfirm({ name, onDone }: { name: string; onDone: () => void }) {
  const del = useDeleteSlo()

  return (
    <div className="flex items-center gap-2 bg-red-900/20 border border-red-700/40 rounded-lg px-3 py-2">
      <span className="text-xs text-red-300">Deactivate <strong>{name}</strong>? All versions will be marked inactive.</span>
      <button
        onClick={() => del.mutate(name, { onSuccess: onDone })}
        disabled={del.isPending}
        className="px-2.5 py-1 text-xs font-medium rounded bg-red-700 text-white hover:bg-red-600 disabled:opacity-40 transition-colors shrink-0"
      >
        {del.isPending ? 'Deactivating…' : 'Confirm'}
      </button>
      <button
        onClick={onDone}
        className="px-2.5 py-1 text-xs rounded border border-slate-600 text-slate-400 hover:text-slate-200 transition-colors shrink-0"
      >
        Cancel
      </button>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export function SloRegistryPage() {
  const { data: slos, isLoading, isError } = useSlos()
  const [expandedSlo, setExpandedSlo] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)
  const [showCreate, setShowCreate] = useState(false)

  // Group sidebar & filtering state
  const [searchParams, setSearchParams] = useSearchParams()
  const selectedGroup = searchParams.get('group')
  const [showAll, setShowAll] = useState(false)
  const { data: groupLinks } = useGroupSloLinks(selectedGroup ?? '')

  // Group CRUD dialog state
  const [createGroupOpen, setCreateGroupOpen] = useState(false)
  const [editGroupName, setEditGroupName] = useState<string | null>(null)
  const [deleteGroupName, setDeleteGroupName] = useState<string | null>(null)

  // SLO link dialog state (two entry points)
  const [linkFromGroup, setLinkFromGroup] = useState<string | null>(null)
  const [linkFromSlo, setLinkFromSlo] = useState<string | null>(null)

  // Filter SLOs based on selected group
  const linkedSloNames = useMemo(() => {
    if (!groupLinks) return null
    return new Set(groupLinks.map(l => l.slo_name))
  }, [groupLinks])

  const filteredSlos = useMemo(() => {
    if (!slos) return []
    if (!selectedGroup || showAll) return slos
    if (!linkedSloNames) return slos
    return slos.filter(s => linkedSloNames.has(s.name))
  }, [slos, selectedGroup, showAll, linkedSloNames])

  const handleSelectGroup = (name: string | null) => {
    setShowAll(false)
    if (name) {
      setSearchParams({ group: name })
    } else {
      setSearchParams({})
    }
  }

  if (isLoading) return <p className="p-6 text-slate-400">Loading...</p>
  if (isError || !slos) return <p className="p-6 text-red-400">Failed to load.</p>

  return (
    <div className="flex h-full">
      <GroupSidebar
        selectedGroup={selectedGroup}
        onSelectGroup={handleSelectGroup}
        onCreateGroup={() => setCreateGroupOpen(true)}
        onEditGroup={(name) => setEditGroupName(name)}
        onDeleteGroup={(name) => setDeleteGroupName(name)}
        onAddSloLink={(groupName) => setLinkFromGroup(groupName)}
      />

      <div className="flex-1 p-6 space-y-4 overflow-y-auto">
        {/* Page header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold text-slate-100">SLO Registry</h1>
            {selectedGroup && !showAll && (
              <span className="text-xs bg-primary/15 text-primary border border-primary/30 px-2 py-0.5 rounded-full">
                filtered: {selectedGroup}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {selectedGroup && (
              <button
                onClick={() => setShowAll(v => !v)}
                className={`px-3 py-1.5 text-xs rounded border transition-colors ${
                  showAll
                    ? 'bg-primary/15 border-primary/40 text-primary'
                    : 'border-slate-700 text-slate-400 hover:border-slate-500 hover:text-slate-200'
                }`}
              >
                {showAll ? 'Show filtered' : 'Show all SLOs'}
              </button>
            )}
            <button
              onClick={() => setShowCreate(v => !v)}
              className={`px-3 py-1.5 text-sm font-medium rounded border transition-colors ${
                showCreate
                  ? 'bg-indigo-600/20 border-indigo-500/50 text-indigo-300'
                  : 'bg-indigo-600 border-indigo-600 text-white hover:bg-indigo-500'
              }`}
            >
              {showCreate ? '\u2715 Cancel' : '+ Create SLO'}
            </button>
          </div>
        </div>

        {/* Inline create panel */}
        {showCreate && (
          <div className="bg-[#111827] border border-indigo-700/40 rounded-xl p-5">
            <h2 className="text-sm font-semibold text-slate-200 mb-4">Create New SLO</h2>
            <SloCreateForm
              onCancel={() => setShowCreate(false)}
              onSaved={() => setShowCreate(false)}
            />
          </div>
        )}

        {/* SLO list */}
        <div className="space-y-2">
          {filteredSlos.map(slo => {
            const tags = (slo.meta?.tags as string[] | undefined) ?? []
            const isExpanded = expandedSlo === slo.name
            const isConfirmingDelete = confirmDelete === slo.name

            return (
              <div
                key={slo.name}
                className={`bg-[#111827] border rounded-xl overflow-hidden transition-colors ${
                  slo.active ? 'border-slate-700' : 'border-slate-800 opacity-60'
                }`}
              >
                {/* Header row */}
                <div className="px-5 py-4 flex items-center gap-4">
                  <button
                    onClick={() => setExpandedSlo(prev => prev === slo.name ? null : slo.name)}
                    className="text-slate-500 text-xs w-3 shrink-0 hover:text-slate-300 transition-colors"
                  >
                    {isExpanded ? '\u25BC' : '\u25B6'}
                  </button>

                  <div
                    className="flex items-center gap-2 min-w-0 flex-1 cursor-pointer"
                    onClick={() => setExpandedSlo(prev => prev === slo.name ? null : slo.name)}
                  >
                    <span className="font-semibold text-slate-100 truncate">
                      {slo.display_name ?? slo.name}
                    </span>
                    <span className="text-xs text-slate-500 shrink-0">v{slo.version}</span>
                    {slo.active
                      ? <span className="text-xs bg-pass/20 text-pass border border-pass/30 px-1.5 py-0.5 rounded-full shrink-0">active</span>
                      : <span className="text-xs bg-slate-700/40 text-slate-500 border border-slate-600/40 px-1.5 py-0.5 rounded-full shrink-0">inactive</span>
                    }
                  </div>

                  {tags.length > 0 && (
                    <div className="flex items-center gap-1 flex-wrap">
                      {tags.map(tag => (
                        <span key={tag} className="text-xs bg-slate-700/60 text-slate-300 px-1.5 py-0.5 rounded">
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}

                  <div className="ml-auto flex items-center gap-4 text-xs text-slate-500 shrink-0">
                    {slo.author && <span>{slo.author}</span>}
                    {slo.notes && (
                      <span className="max-w-xs truncate text-slate-600 italic" title={slo.notes}>
                        {slo.notes}
                      </span>
                    )}
                    <span className="text-slate-600">{slo.created_at.slice(0, 10)}</span>

                    {slo.active && (
                      <button
                        onClick={e => { e.stopPropagation(); setLinkFromSlo(slo.name) }}
                        className="text-xs text-slate-500 hover:text-primary transition-colors border border-transparent hover:border-primary/40 px-1.5 py-0.5 rounded"
                        title="Link to asset group"
                      >
                        + Group
                      </button>
                    )}

                    {slo.active && (
                      <button
                        onClick={e => { e.stopPropagation(); setConfirmDelete(slo.name) }}
                        className="text-xs text-slate-600 hover:text-red-400 transition-colors border border-transparent hover:border-red-700/40 px-1.5 py-0.5 rounded"
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

          {filteredSlos.length === 0 && selectedGroup && !showAll && (
            <div className="text-center py-8 text-slate-500 text-sm">
              No SLOs linked to this group.{' '}
              <button
                onClick={() => setShowAll(true)}
                className="text-primary hover:underline"
              >
                Show all SLOs
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Group CRUD Dialogs */}
      <GroupCreateDialog
        open={createGroupOpen}
        onOpenChange={setCreateGroupOpen}
      />
      <GroupEditDialog
        open={editGroupName !== null}
        onOpenChange={(open) => { if (!open) setEditGroupName(null) }}
        groupName={editGroupName}
      />
      <GroupDeleteDialog
        open={deleteGroupName !== null}
        onOpenChange={(open) => { if (!open) setDeleteGroupName(null) }}
        groupName={deleteGroupName}
        onDeleted={() => {
          if (deleteGroupName === selectedGroup) handleSelectGroup(null)
          setDeleteGroupName(null)
        }}
      />

      {/* SLO Link Dialogs — group entry point */}
      <SloLinkDialog
        open={linkFromGroup !== null}
        onOpenChange={(open) => { if (!open) setLinkFromGroup(null) }}
        lockedGroupName={linkFromGroup ?? undefined}
      />

      {/* SLO Link Dialogs — SLO entry point */}
      <SloLinkDialog
        open={linkFromSlo !== null}
        onOpenChange={(open) => { if (!open) setLinkFromSlo(null) }}
        lockedSloName={linkFromSlo ?? undefined}
      />
    </div>
  )
}
