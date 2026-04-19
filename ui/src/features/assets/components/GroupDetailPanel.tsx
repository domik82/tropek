// ui/src/features/assets/components/GroupDetailPanel.tsx
import { useState } from 'react'
import { Pencil, Link, Trash2, X, FolderPlus, Plus } from 'lucide-react'
import { LabelChips } from '@/components/labels/LabelChips'
import { LabelsEditorDialog } from '@/components/labels/LabelsEditorDialog'
import { useAssetGroup, useAssets, useRemoveGroupMember, useAssetGroups, useUpdateAsset } from '../hooks'
import { useGroupSloAssignments, useDeleteGroupSloAssignment } from '@/features/slos/hooks'
import { GroupEditDialog } from './GroupEditDialog'
import { GroupDeleteDialog } from './GroupDeleteDialog'
import { GroupCreateDialog } from './GroupCreateDialog'
import { SANS_SERIF } from '@/lib/fonts'
import { SloLinkDialog } from '@/features/slos/components/SloLinkDialog'
import { AddAssetToGroupDialog } from './AddAssetToGroupDialog'
import { AssetEditDialog } from './AssetEditDialog'
import type { AssetGroup } from '../domain'

interface Props {
  groupName: string
  onSelectGroup: (name: string) => void
  selectedAsset?: string | null
}

export function GroupDetailPanel({ groupName, onSelectGroup, selectedAsset }: Props) {
  const { data: group } = useAssetGroup(groupName)
  const { data: tree } = useAssetGroups()
  const { data: assets = [] } = useAssets()
  const { data: assignments = [] } = useGroupSloAssignments(groupName)
  const removeMember = useRemoveGroupMember()
  const unlinkSlo = useDeleteGroupSloAssignment()
  const updateAsset = useUpdateAsset()

  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [createSubgroupOpen, setCreateSubgroupOpen] = useState(false)
  const [linkSloOpen, setLinkSloOpen] = useState(false)
  const [addAssetOpen, setAddAssetOpen] = useState(false)
  const [editingAssetName, setEditingAssetName] = useState<string | null>(null)
  const [labelEditAsset, setLabelEditAsset] = useState<{ name: string; tags: Record<string, string> } | null>(null)

  if (!group) {
    return <div className="p-6 text-muted-foreground">Loading…</div>
  }

  // Resolve subgroups from tree
  const subgroups: AssetGroup[] = tree
    ? group.subgroups
        .map(sg => tree.allGroups.find(g => g.id === sg.groupId))
        .filter((g): g is AssetGroup => g !== undefined)
    : []

  // Resolve member assets
  const memberAssets = group.members.map(m => ({
    ...m,
    asset: assets.find(a => a.id === m.assetId),
  }))

  const statsLine = [
    `${group.members.length} assets`,
    `${subgroups.length} subgroups`,
    `${assignments.length} linked SLOs`,
  ].join(' · ')

  return (
    <div
      className="p-6 space-y-6"
      style={{ fontFamily: SANS_SERIF }}
    >
      {/* Header */}
      <div>
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-xl font-semibold text-foreground">
              {group.displayName ?? group.name}
            </h2>
            <p className="text-sm text-muted-foreground mt-0.5">{statsLine}</p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setEditDialogOpen(true)}
              className="px-3 py-1.5 text-xs rounded border border-border text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1.5"
            >
              <Pencil className="w-3.5 h-3.5" />
              Edit
            </button>
            <button
              onClick={() => setLinkSloOpen(true)}
              className="px-3 py-1.5 text-xs rounded bg-action-primary-bg border border-action-primary-border text-action-primary hover:bg-action-primary-hover transition-colors flex items-center gap-1.5"
            >
              <Link className="w-3.5 h-3.5" />
              Link SLO
            </button>
            <button
              onClick={() => setDeleteDialogOpen(true)}
              className="px-3 py-1.5 text-xs rounded bg-action-destructive-bg border border-action-destructive-border text-action-destructive hover:bg-action-destructive-bg transition-colors flex items-center gap-1.5"
            >
              <Trash2 className="w-3.5 h-3.5" />
              Delete
            </button>
          </div>
        </div>
        {group.description && (
          <p className="text-sm text-muted-foreground mt-2">{group.description}</p>
        )}
      </div>

      {/* Subgroups */}
      <div>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-foreground">
              Subgroups ({subgroups.length})
            </h3>
            <button
              onClick={() => setCreateSubgroupOpen(true)}
              className="px-2.5 py-1 text-xs rounded border border-action-primary-border bg-action-primary-bg text-action-primary hover:bg-action-primary-hover flex items-center gap-1"
            >
              <FolderPlus className="w-3 h-3" />
              Add Subgroup
            </button>
          </div>
          {subgroups.length === 0 && (
            <p className="text-sm text-muted-foreground italic">No subgroups</p>
          )}
          <div className="flex flex-wrap gap-3">
            {subgroups.map(sg => (
              <button
                key={sg.id}
                onClick={() => onSelectGroup(sg.name)}
                className="bg-card border border-border rounded-lg border-t-[3px] border-t-indicator-default p-3 min-w-[160px] text-left hover:bg-muted/30 transition-colors"
              >
                <p className="text-sm font-medium text-foreground">{sg.displayName ?? sg.name}</p>
                <p className="text-xs text-muted-foreground mt-1">{sg.members.length} assets</p>
              </button>
            ))}
          </div>
        </div>

      {/* Direct Members */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-foreground">
            Direct Members ({group.members.length})
          </h3>
          <button
            onClick={() => setAddAssetOpen(true)}
            className="px-2.5 py-1 text-xs rounded border border-action-primary-border bg-action-primary-bg text-action-primary hover:bg-action-primary-hover flex items-center gap-1"
          >
            <Plus className="w-3 h-3" />
            Add Asset to Group
          </button>
        </div>
        {group.members.length === 0 && (
          <p className="text-sm text-muted-foreground italic">No members</p>
        )}
        {group.members.length > 0 && (
          <div className="border border-border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-table-header-bg">
                  <th className="text-left px-3 py-2 text-xs uppercase text-muted-foreground font-medium">Name</th>
                  <th className="text-left px-3 py-2 text-xs uppercase text-muted-foreground font-medium">Type</th>
                  <th className="text-left px-3 py-2 text-xs uppercase text-muted-foreground font-medium min-w-[200px]">Labels</th>
                  <th className="text-center px-3 py-2 text-xs uppercase text-muted-foreground font-medium w-[60px]">Weight</th>
                  <th className="text-center px-3 py-2 text-xs uppercase text-muted-foreground font-medium w-[80px]">Actions</th>
                </tr>
              </thead>
              <tbody>
                {memberAssets.map(({ assetId, assetName, weight, asset }, idx) => {
                  const isHighlighted = selectedAsset === assetName
                  return (
                  <tr key={assetId} className={`border-b border-border/60 last:border-0 hover:bg-table-row-hover transition-colors ${isHighlighted ? 'bg-table-row-selected' : idx % 2 === 0 ? 'bg-table-row-bg' : 'bg-table-row-alt'}`}>
                    <td className="px-3 py-2">
                      <span className="font-mono text-foreground">{asset?.displayName ?? assetName}</span>
                      {asset?.displayName && (
                        <span className="text-xs text-muted-foreground ml-1.5">{assetName}</span>
                      )}
                    </td>
                    <td className="px-3 py-2 font-mono text-muted-foreground">
                      {asset?.typeName ?? '—'}
                    </td>
                    <td className="px-3 py-2">
                      <LabelChips
                        labels={asset?.tags ?? {}}
                        maxVisible={3}
                        size="small"
                        onEdit={() => setLabelEditAsset({ name: assetName, tags: asset?.tags ?? {} })}
                      />
                    </td>
                    <td className="px-3 py-2 text-center font-mono text-muted-foreground">
                      {weight}
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex items-center justify-center gap-1">
                        <button
                          onClick={() => setEditingAssetName(assetName)}
                          className="p-1 text-action-primary hover:bg-action-primary-hover rounded transition-colors"
                          title="Edit asset"
                        >
                          <Pencil className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => removeMember.mutate({ groupName, assetId })}
                          className="p-1 text-action-destructive hover:bg-action-destructive-bg rounded transition-colors"
                          title="Remove from group"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Linked SLOs */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-foreground">
            Linked SLOs ({assignments.length})
          </h3>
          <button
            onClick={() => setLinkSloOpen(true)}
            className="px-2.5 py-1 text-xs rounded border border-action-primary-border bg-action-primary-bg text-action-primary hover:bg-action-primary-hover flex items-center gap-1"
          >
            <Link className="w-3 h-3" />
            Link SLO
          </button>
        </div>
        {assignments.length === 0 && (
          <p className="text-sm text-muted-foreground italic">No linked SLOs</p>
        )}
        {assignments.length > 0 && (
          <div className="border border-border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-table-header-bg">
                  <th className="text-left px-3 py-2 text-xs uppercase text-muted-foreground font-medium">SLO Name</th>
                  <th className="text-left px-3 py-2 text-xs uppercase text-muted-foreground font-medium">Datasource</th>
                  <th className="text-center px-3 py-2 text-xs uppercase text-muted-foreground font-medium w-[60px]"></th>
                </tr>
              </thead>
              <tbody>
                {assignments.map((assignment, idx) => (
                  <tr key={assignment.id} className={`border-b border-border/60 last:border-0 hover:bg-table-row-hover transition-colors ${idx % 2 === 0 ? 'bg-table-row-bg' : 'bg-table-row-alt'}`}>
                    <td className="px-3 py-2 font-medium text-foreground">{assignment.sloName}</td>
                    <td className="px-3 py-2 text-muted-foreground/60">{assignment.dataSourceName}</td>
                    <td className="px-3 py-2 text-center">
                      <button
                        onClick={() => unlinkSlo.mutate({ groupName, sloDefinitionId: assignment.sloDefinitionId })}
                        className="p-1 text-muted-foreground hover:text-action-destructive transition-colors"
                        title="Unlink"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Dialogs */}
      <GroupEditDialog
        open={editDialogOpen}
        onOpenChange={setEditDialogOpen}
        groupName={groupName}
      />
      <GroupDeleteDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        groupName={groupName}
        onDeleted={() => onSelectGroup('__ungrouped__')}
      />
      <GroupCreateDialog
        open={createSubgroupOpen}
        onOpenChange={setCreateSubgroupOpen}
      />
      <SloLinkDialog
        open={linkSloOpen}
        onOpenChange={setLinkSloOpen}
        lockedGroupName={groupName}
      />
      <AddAssetToGroupDialog
        open={addAssetOpen}
        onOpenChange={setAddAssetOpen}
        groupName={groupName}
      />
      <AssetEditDialog
        open={editingAssetName !== null}
        onOpenChange={open => { if (!open) setEditingAssetName(null) }}
        assetName={editingAssetName}
      />
      <LabelsEditorDialog
        open={labelEditAsset !== null}
        onOpenChange={open => { if (!open) setLabelEditAsset(null) }}
        title="Edit Labels"
        subtitle={labelEditAsset?.name ?? ''}
        labels={labelEditAsset?.tags ?? {}}
        onSave={tags => {
          if (labelEditAsset) {
            updateAsset.mutate({ name: labelEditAsset.name, tags })
          }
          setLabelEditAsset(null)
        }}
      />
    </div>
  )
}
