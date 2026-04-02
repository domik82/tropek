import { useState } from 'react'
import { Plus, RefreshCw, Trash2, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { DeletionConfirmForm } from '@/components/DeletionConfirmForm'
import { ENTITY_COLORS } from '@/lib/entity-colors'
import { SANS_SERIF } from '@/lib/fonts'
import { useSloGroupDetail, useDeleteSloGroup, useUpdateSloGroup } from '@/features/slo-groups/hooks'
import { useSloVersions } from '@/features/slos/hooks'
import type { SelectedNode } from '@/features/registry/types'

interface Props {
  name: string
  onNavigate: (node: SelectedNode) => void
}

export function SloGroupDetailView({ name, onNavigate }: Props) {
  const [showDelete, setShowDelete] = useState(false)
  const [showRegenerate, setShowRegenerate] = useState(false)
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null)
  const [editVars, setEditVars] = useState<Record<string, string[]> | null>(null)
  const { data: group, isLoading } = useSloGroupDetail(name)
  const deleteMutation = useDeleteSloGroup()
  const updateMutation = useUpdateSloGroup()
  const { data: versions } = useSloVersions(group?.template_slo_name ?? '', showRegenerate && !!group)

  if (isLoading || !group) {
    return (
      <div className="p-4 text-sm text-muted-foreground" style={{ fontFamily: SANS_SERIF }}>
        Loading...
      </div>
    )
  }

  function handleDelete(_reason: string, _author: string) {
    deleteMutation.mutate(group!.name)
    setShowDelete(false)
  }

  // Compute variable rows: transpose gen_variables map into row-oriented data
  const varKeys = Object.keys(group.gen_variables)
  const rowCount = Math.max(0, ...varKeys.map(k => group.gen_variables[k].length))
  const rows = Array.from({ length: rowCount }, (_, i) =>
    varKeys.map(k => group.gen_variables[k][i] ?? ''),
  )

  return (
    <div className="overflow-auto h-full" style={{ fontFamily: SANS_SERIF }}>
      <div className="h-[3px]" style={{ backgroundColor: ENTITY_COLORS.sloGroup }} />
      <div className="p-6 space-y-6">
        {/* Header */}
        <div>
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <h2 className="text-xl font-semibold text-foreground truncate">
                {group.display_name ?? group.name}
              </h2>
              <p className="text-xs font-mono text-muted-foreground mt-0.5">{group.name}</p>
            </div>
            <span className="px-2 py-0.5 text-xs rounded-full border border-border bg-muted/40 text-muted-foreground shrink-0">
              v{group.version}
            </span>
          </div>

          <div className="flex gap-2 mt-3">
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                setShowRegenerate(true)
                setShowDelete(false)
                setEditVars(JSON.parse(JSON.stringify(group.gen_variables)))
              }}
            >
              <RefreshCw className="size-3.5" />
              New Version
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="text-red-400 border-red-700/40 hover:bg-red-950/20"
              onClick={() => { setShowDelete(true); setShowRegenerate(false) }}
            >
              <Trash2 className="size-3.5" />
              Delete Group
            </Button>
          </div>

          {showRegenerate && editVars && (() => {
            const editKeys = Object.keys(editVars)
            const editRowCount = Math.max(0, ...editKeys.map(k => editVars[k].length))

            function updateCell(key: string, rowIdx: number, value: string) {
              setEditVars(prev => {
                if (!prev) return prev
                const next = { ...prev, [key]: [...prev[key]] }
                next[key][rowIdx] = value
                return next
              })
            }

            function addRow() {
              setEditVars(prev => {
                if (!prev) return prev
                const next: Record<string, string[]> = {}
                for (const k of Object.keys(prev)) {
                  next[k] = [...prev[k], '']
                }
                return next
              })
            }

            function removeRow(rowIdx: number) {
              setEditVars(prev => {
                if (!prev) return prev
                const next: Record<string, string[]> = {}
                for (const k of Object.keys(prev)) {
                  next[k] = prev[k].filter((_, i) => i !== rowIdx)
                }
                return next
              })
            }

            const varsChanged = JSON.stringify(editVars) !== JSON.stringify(group.gen_variables)
            const versionChanged = selectedVersion !== null && selectedVersion !== group.template_slo_version
            const hasEmptyCells = editKeys.some(k => editVars[k].some(v => v.trim() === ''))

            return (
              <div className="mt-3 p-3 border border-border rounded bg-muted/20 space-y-3">
                <p className="text-xs text-muted-foreground">
                  Edit variables and/or pick a template version, then regenerate.
                </p>

                {/* Version picker */}
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">Template version:</span>
                  {versions && versions.length > 0 ? (
                    <select
                      className="text-xs bg-background border border-border rounded px-2 py-1 text-foreground"
                      value={selectedVersion ?? group.template_slo_version}
                      onChange={e => setSelectedVersion(Number(e.target.value))}
                    >
                      {versions.map(v => (
                        <option key={v.version} value={v.version}>
                          v{v.version}{v.version === group.template_slo_version ? ' (current)' : ''}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <span className="text-xs text-muted-foreground">v{group.template_slo_version} (loading…)</span>
                  )}
                </div>

                {/* Editable variables table */}
                {editKeys.length > 0 && (
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">Variables</p>
                    <div className="border border-border rounded overflow-hidden">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="bg-muted/30">
                            {editKeys.map(k => (
                              <th key={k} className="text-left px-2 py-1 text-muted-foreground font-medium">{k}</th>
                            ))}
                            <th className="w-6" />
                          </tr>
                        </thead>
                        <tbody>
                          {Array.from({ length: editRowCount }, (_, i) => (
                            <tr key={i} className="border-t border-border/50">
                              {editKeys.map(k => (
                                <td key={k} className="px-1 py-0.5">
                                  <input
                                    className="w-full text-xs font-mono bg-background border border-border/50 rounded px-1.5 py-0.5 text-foreground focus:outline-none focus:border-primary"
                                    value={editVars[k][i] ?? ''}
                                    onChange={e => updateCell(k, i, e.target.value)}
                                  />
                                </td>
                              ))}
                              <td className="px-1 py-0.5">
                                {editRowCount > 1 && (
                                  <button
                                    className="text-muted-foreground hover:text-red-400 p-0.5"
                                    onClick={() => removeRow(i)}
                                    title="Remove row"
                                  >
                                    <X className="size-3" />
                                  </button>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <button
                      className="flex items-center gap-1 text-xs text-primary hover:underline mt-1.5"
                      onClick={addRow}
                    >
                      <Plus className="size-3" />
                      Add row
                    </button>
                  </div>
                )}

                {/* Actions */}
                <div className="flex items-center gap-2">
                  <Button
                    size="xs"
                    disabled={hasEmptyCells || updateMutation.isPending}
                    onClick={() => {
                      const body: Record<string, unknown> = {}
                      if (versionChanged && selectedVersion) body.template_slo_version = selectedVersion
                      if (varsChanged) body.gen_variables = editVars
                      updateMutation.mutate(
                        { name: group.name, body },
                        {
                          onSuccess: () => {
                            setShowRegenerate(false)
                            setSelectedVersion(null)
                            setEditVars(null)
                          },
                        },
                      )
                    }}
                  >
                    <RefreshCw className={`size-3 ${updateMutation.isPending ? 'animate-spin' : ''}`} />
                    {updateMutation.isPending ? 'Regenerating…' : 'Regenerate'}
                  </Button>
                  <Button
                    size="xs"
                    variant="ghost"
                    onClick={() => { setShowRegenerate(false); setSelectedVersion(null); setEditVars(null) }}
                  >
                    Cancel
                  </Button>
                </div>

                {updateMutation.isError && (
                  <p className="text-xs text-red-400">
                    {updateMutation.error instanceof Error ? updateMutation.error.message : 'Regeneration failed'}
                  </p>
                )}
              </div>
            )
          })()}

          {showDelete && (
            <div className="mt-3">
              <DeletionConfirmForm
                title={`Delete group "${group.name}"?`}
                onConfirm={handleDelete}
                onCancel={() => setShowDelete(false)}
                confirmLabel="Delete"
                pendingLabel="Deleting…"
                isPending={deleteMutation.isPending}
                requireReason={false}
              />
            </div>
          )}
        </div>

        {/* Template link */}
        <div>
          <p className="text-xs text-muted-foreground mb-1">Template SLO</p>
          <button
            className="text-sm text-primary hover:underline"
            onClick={() => onNavigate({ type: 'template', name: group.template_slo_name })}
          >
            {group.template_slo_name} v{group.template_slo_version}
          </button>
        </div>

        {/* Generated count */}
        <div>
          <p className="text-sm text-foreground">{group.generated_slo_count} SLOs generated</p>
        </div>

        {/* Gen variables table */}
        {varKeys.length > 0 && (
          <div>
            <p className="text-xs text-muted-foreground mb-2">Generator Variables</p>
            <div className="border border-border rounded overflow-hidden">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-muted/30">
                    {varKeys.map(k => (
                      <th
                        key={k}
                        className="text-left px-3 py-1.5 text-muted-foreground font-medium"
                      >
                        {k}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, i) => (
                    <tr key={i} className="border-t border-border/50">
                      {row.map((val, j) => (
                        <td key={j} className="px-3 py-1.5 text-foreground font-mono">
                          {val}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Tags */}
        {Object.keys(group.tags).length > 0 && (
          <div>
            <p className="text-xs text-muted-foreground mb-2">Tags</p>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(group.tags).map(([k, v]) => (
                <span
                  key={k}
                  className="px-2 py-0.5 text-xs rounded-full bg-primary/10 text-primary border border-primary/20"
                >
                  {k}: {v}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Author */}
        {group.author && (
          <div>
            <p className="text-xs text-muted-foreground mb-1">Author</p>
            <p className="text-sm text-foreground">{group.author}</p>
          </div>
        )}
      </div>
    </div>
  )
}
