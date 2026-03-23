import { useState, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { SANS_SERIF } from '@/lib/fonts'
import { RegistrySidebar } from '@/features/registry/RegistrySidebar'
import { RegistryDetailPanel } from '@/features/registry/RegistryDetailPanel'
import { SloWizard } from '@/features/registry/forms/SloWizard'
import { DatasourceForm } from '@/features/registry/forms/DatasourceForm'
import { SliForm } from '@/features/registry/forms/SliForm'
import { SloLinkDialogRevised } from '@/features/registry/forms/SloLinkDialogRevised'
import { useCreateGroup } from '@/features/slos/hooks'
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
  const [sliFormOpen, setSliFormOpen] = useState(false)
  const [sliDefaultAdapter, setSliDefaultAdapter] = useState<string | undefined>()
  const [linkDialogOpen, setLinkDialogOpen] = useState(false)
  const [linkLockedGroup, setLinkLockedGroup] = useState<string | undefined>()

  // SloWizard state (replaces detail panel, not a dialog)
  const [wizardOpen, setWizardOpen] = useState(false)
  const [wizardEditSlo, setWizardEditSlo] = useState<SloDefinition | undefined>()

  const createGroup = useCreateGroup()

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
          setDsFormOpen(true)
          break
        case 'group': {
          const name = window.prompt('New group name:')
          if (name?.trim()) {
            createGroup.mutateAsync({ name: name.trim() })
          }
          break
        }
      }
    },
    [createGroup],
  )

  const handleEditDatasource = useCallback((_name: string) => {
    // TODO: look up DataSource by name and pass as editFrom
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

  return (
    <div className="flex h-full" style={{ fontFamily: SANS_SERIF }}>
      <RegistrySidebar
        mode={mode}
        onModeChange={handleModeChange}
        selected={selected}
        onSelect={handleSelect}
        onCreateAction={handleCreateAction}
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
          />
        )}
      </div>

      {/* Dialog forms */}
      <DatasourceForm open={dsFormOpen} onOpenChange={setDsFormOpen} />
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
    </div>
  )
}
