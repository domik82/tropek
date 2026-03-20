// src/pages/SloRegistryPage.tsx
import { useState, useMemo, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useSlos, useGroupSloLinks, useGroupTree } from '@/features/slos/hooks'
import { SloCreateForm } from '@/features/slos/components/SloCreateForm'
import { SloList } from '@/features/slos/components/SloList'
import { SloGroupDialogs } from '@/features/slos/components/SloGroupDialogs'
import { AssetTree } from '@/components/AssetTree'

export function SloRegistryPage() {
  const { data: slos, isLoading, isError } = useSlos()
  const [showCreate, setShowCreate] = useState(false)

  // Group sidebar & filtering state
  const [searchParams, setSearchParams] = useSearchParams()
  const selectedGroup = searchParams.get('group')
  const [showAll, setShowAll] = useState(false)
  const { data: tree } = useGroupTree()
  const { data: groupLinks } = useGroupSloLinks(selectedGroup ?? '')

  // Clear stale group param if it doesn't exist in the tree
  useEffect(() => {
    if (!selectedGroup || selectedGroup === '__ungrouped__' || !tree) return
    const exists = tree.all_groups.some(g => g.name === selectedGroup)
    if (!exists) setSearchParams({})
  }, [selectedGroup, tree, setSearchParams])

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
      <AssetTree
        mode="slo"
        selectedGroup={selectedGroup}
        onSelectGroup={handleSelectGroup}
        onCreateGroup={() => setCreateGroupOpen(true)}
        onEditGroup={name => setEditGroupName(name)}
        onDeleteGroup={name => setDeleteGroupName(name)}
        onAddSloLink={groupName => setLinkFromGroup(groupName)}
        width={220}
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
        <SloList
          slos={filteredSlos}
          selectedGroup={selectedGroup}
          showAll={showAll}
          onShowAll={() => setShowAll(true)}
          onLinkSlo={name => setLinkFromSlo(name)}
        />
      </div>

      {/* Dialogs */}
      <SloGroupDialogs
        createGroupOpen={createGroupOpen}
        onCloseCreateGroup={() => setCreateGroupOpen(false)}
        editGroupName={editGroupName}
        onCloseEditGroup={() => setEditGroupName(null)}
        deleteGroupName={deleteGroupName}
        onCloseDeleteGroup={() => setDeleteGroupName(null)}
        onGroupDeleted={() => {
          if (deleteGroupName === selectedGroup) handleSelectGroup(null)
          setDeleteGroupName(null)
        }}
        linkFromGroup={linkFromGroup}
        onCloseLinkFromGroup={() => setLinkFromGroup(null)}
        linkFromSlo={linkFromSlo}
        onCloseLinkFromSlo={() => setLinkFromSlo(null)}
      />
    </div>
  )
}
