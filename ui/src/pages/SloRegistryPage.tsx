import { useState, useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { SANS_SERIF } from '@/lib/fonts'
import { ENTITY_COLORS } from '@/lib/entity-colors'
import { RegistrySidebar } from '@/features/registry/RegistrySidebar'
import { RegistryDetailPanel } from '@/features/registry/RegistryDetailPanel'
import { SloWizard } from '@/features/registry/forms/SloWizard'
import { DatasourceForm } from '@/features/registry/forms/DatasourceForm'
import { SliForm } from '@/features/registry/forms/SliForm'
import { SloLinkDialogRevised } from '@/features/registry/forms/SloLinkDialogRevised'
import { useCreateGroup, useGroupTree } from '@/features/slos/hooks'
import { useAllGroupLinks } from '@/features/registry/useAllGroupLinks'
import { useDatasource } from '@/features/datasources/hooks'
import type { RegistryMode, SelectedNode } from '@/features/registry/types'
import type { SloDefinition } from '@/features/slos/types'

export function SloRegistryPage() {
  const [searchParams, setSearchParams] = useSearchParams()

  // URL-persisted state
  const mode = (searchParams.get('mode') as RegistryMode) || 'asset'
  const selectedName = searchParams.get('selected')
  const selectedType = searchParams.get('type')
  const selectedGroup = searchParams.get('group')

  const selected: SelectedNode | null =
    selectedName && selectedType
      ? { name: selectedName, type: selectedType as SelectedNode['type'], groupName: selectedGroup ?? undefined }
      : null

  // Form dialog state
  const [dsFormOpen, setDsFormOpen] = useState(false)
  const [dsEditName, setDsEditName] = useState<string | undefined>()
  const [sliFormOpen, setSliFormOpen] = useState(false)
  const [sliDefaultAdapter, setSliDefaultAdapter] = useState<string | undefined>()
  const [linkDialogOpen, setLinkDialogOpen] = useState(false)
  const [linkLockedGroup, setLinkLockedGroup] = useState<string | undefined>()

  // Group creation dialog state
  const [groupDialogOpen, setGroupDialogOpen] = useState(false)
  const [groupName, setGroupName] = useState('')

  // SloWizard state (replaces detail panel, not a dialog)
  const [wizardOpen, setWizardOpen] = useState(false)
  const [wizardEditSlo, setWizardEditSlo] = useState<SloDefinition | undefined>()

  // Fetch datasource for edit mode
  const { data: dsEditFrom } = useDatasource(dsEditName ?? '')
  const createGroup = useCreateGroup()

  const { data: tree } = useGroupTree()
  const groupNames = useMemo(
    () => (tree?.all_groups ?? []).map(g => g.name),
    [tree],
  )
  const { allLinks, groupLinksMap } = useAllGroupLinks(groupNames)

  const updateParams = useCallback(
    (updates: Record<string, string | null>) => {
      setSearchParams(prev => {
        const next = new URLSearchParams(prev)
        for (const [k, v] of Object.entries(updates)) {
          if (v === null) next.delete(k)
          else next.set(k, v)
        }
        return next
      })
    },
    [setSearchParams],
  )

  const handleModeChange = useCallback(
    (newMode: RegistryMode) => {
      updateParams({ mode: newMode, selected: null, type: null, group: null })
      setWizardOpen(false)
    },
    [updateParams],
  )

  const handleSelect = useCallback(
    (node: SelectedNode) => {
      updateParams({
        selected: node.name,
        type: node.type,
        group: node.groupName ?? null,
      })
      setWizardOpen(false)
    },
    [updateParams],
  )

  const handleNavigate = useCallback(
    (node: SelectedNode) => {
      // Switch mode based on target type
      let targetMode: RegistryMode = mode
      if (node.type === 'slo' || node.type === 'sli') targetMode = 'slo'
      else if (node.type === 'datasource') targetMode = 'datasource'
      else targetMode = 'asset'

      updateParams({
        mode: targetMode,
        selected: node.name,
        type: node.type,
        group: node.groupName ?? null,
      })
      setWizardOpen(false)
    },
    [mode, updateParams],
  )

  const handleCreateAction = useCallback(
    (type: 'datasource' | 'sli' | 'slo' | 'group', context?: { adapterType?: string }) => {
      switch (type) {
        case 'slo':
          setWizardEditSlo(undefined)
          setWizardOpen(true)
          break
        case 'sli':
          setSliDefaultAdapter(context?.adapterType)
          setSliFormOpen(true)
          break
        case 'datasource':
          setDsEditName(undefined)
          setDsFormOpen(true)
          break
        case 'group':
          setGroupName('')
          setGroupDialogOpen(true)
          break
      }
    },
    [],
  )

  const handleEditDatasource = useCallback((name: string) => {
    setDsEditName(name)
    setDsFormOpen(true)
  }, [])

  const handleNewSloVersion = useCallback((slo: SloDefinition) => {
    setWizardEditSlo(slo)
    setWizardOpen(true)
  }, [])

  const handleLinkSlo = useCallback((groupName: string) => {
    setLinkLockedGroup(groupName)
    setLinkDialogOpen(true)
  }, [])

  const handleWizardClose = useCallback(() => {
    setWizardOpen(false)
    setWizardEditSlo(undefined)
  }, [])

  function handleGroupCreate() {
    const trimmed = groupName.trim()
    if (!trimmed) return
    createGroup.mutate(
      { name: trimmed },
      { onSuccess: () => { setGroupDialogOpen(false); setGroupName('') } },
    )
  }

  return (
    <div className="flex h-full" style={{ fontFamily: SANS_SERIF }}>
      <RegistrySidebar
        mode={mode}
        onModeChange={handleModeChange}
        selected={selected}
        onSelect={handleSelect}
        onCreateAction={handleCreateAction}
        allLinks={allLinks}
        groupLinksMap={groupLinksMap}
      />

      <div className="flex-1 overflow-y-auto">
        {wizardOpen ? (
          <SloWizard editSlo={wizardEditSlo} onClose={handleWizardClose} />
        ) : (
          <RegistryDetailPanel
            selected={selected}
            onNavigate={handleNavigate}
            onEditDatasource={handleEditDatasource}
            onNewSloVersion={handleNewSloVersion}
            onLinkSlo={handleLinkSlo}
            groupLinksMap={groupLinksMap}
          />
        )}
      </div>

      {/* Dialog forms */}
      <DatasourceForm
        open={dsFormOpen}
        onOpenChange={(open) => { setDsFormOpen(open); if (!open) setDsEditName(undefined) }}
        editFrom={dsEditName ? dsEditFrom : undefined}
      />
      <SliForm
        open={sliFormOpen}
        onOpenChange={setSliFormOpen}
        defaultAdapterType={sliDefaultAdapter}
      />
      <SloLinkDialogRevised
        open={linkDialogOpen}
        onOpenChange={setLinkDialogOpen}
        lockedGroupName={linkLockedGroup}
      />

      {/* Group creation dialog */}
      <Dialog open={groupDialogOpen} onOpenChange={setGroupDialogOpen}>
        <DialogContent className="sm:max-w-sm" style={{ fontFamily: SANS_SERIF }}>
          <div className="h-[3px] -mx-6 -mt-6 mb-0 rounded-t-lg overflow-hidden" style={{ backgroundColor: ENTITY_COLORS.group }} />
          <DialogHeader>
            <DialogTitle>New Asset Group</DialogTitle>
          </DialogHeader>
          <div>
            <label htmlFor="group-name" className="block text-xs text-muted-foreground mb-1">
              Name
            </label>
            <Input
              id="group-name"
              value={groupName}
              onChange={(e) => setGroupName(e.target.value)}
              placeholder="my-asset-group"
              onKeyDown={(e) => { if (e.key === 'Enter') handleGroupCreate() }}
            />
          </div>
          <DialogFooter>
            <Button size="xs" variant="outline" onClick={() => setGroupDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              size="xs"
              disabled={!groupName.trim() || createGroup.isPending}
              onClick={handleGroupCreate}
            >
              {createGroup.isPending ? 'Creating…' : 'Create'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
