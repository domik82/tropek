import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { ENTITY_COLORS } from '@/lib/entity-colors'
import { SANS_SERIF } from '@/lib/fonts'
import { useSlos } from '@/features/slos/hooks'
import { useCreateSloGroup } from '@/features/slo-groups/hooks'

interface Props {
  onClose: () => void
}

export function SloGroupForm({ onClose }: Props) {
  const { data: slos } = useSlos()
  const createMutation = useCreateSloGroup()

  const [name, setName] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [templateSloName, setTemplateSloName] = useState('')
  const [genVarsText, setGenVarsText] = useState('')

  const templateSlos = (slos ?? []).filter(s => s.kind === 'template' && s.active)
  const selectedTemplate = templateSlos.find(t => t.name === templateSloName)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!name || !templateSloName || !selectedTemplate) return

    // Parse gen_variables: key=val1,val2,val3 (one per line)
    const genVariables: Record<string, string[]> = {}
    for (const line of genVarsText.split('\n').filter(l => l.trim())) {
      const [key, ...rest] = line.split('=')
      if (key && rest.length > 0) {
        genVariables[key.trim()] = rest.join('=').split(',').map(v => v.trim())
      }
    }

    await createMutation.mutateAsync({
      name,
      display_name: displayName || undefined,
      template_slo_name: templateSloName,
      template_slo_version: selectedTemplate.version,
      gen_variables: genVariables,
    })
    onClose()
  }

  return (
    <div className="overflow-auto h-full" style={{ fontFamily: SANS_SERIF }}>
      <div className="h-[3px]" style={{ backgroundColor: ENTITY_COLORS.sloGroup }} />
      <form onSubmit={handleSubmit} className="p-6 space-y-4">
        <h2 className="text-lg font-semibold text-foreground">New SLO Group</h2>

        <div>
          <label htmlFor="group-name" className="block text-xs text-muted-foreground mb-1">
            Name
          </label>
          <input
            id="group-name"
            type="text"
            value={name}
            onChange={e => setName(e.target.value)}
            className="w-full px-3 py-1.5 text-sm bg-muted/30 border border-border rounded text-foreground"
            placeholder="app-x-plugins"
          />
        </div>

        <div>
          <label htmlFor="group-display" className="block text-xs text-muted-foreground mb-1">
            Display Label
          </label>
          <input
            id="group-display"
            type="text"
            value={displayName}
            onChange={e => setDisplayName(e.target.value)}
            className="w-full px-3 py-1.5 text-sm bg-muted/30 border border-border rounded text-foreground"
            placeholder="App-X Plugin Monitoring"
          />
        </div>

        <div>
          <p className="text-xs text-muted-foreground mb-1">Template SLO</p>
          <select
            value={templateSloName}
            onChange={e => setTemplateSloName(e.target.value)}
            className="w-full px-3 py-1.5 text-sm bg-muted/30 border border-border rounded text-foreground"
          >
            <option value="">Select a template...</option>
            {templateSlos.map(t => (
              <option key={t.name} value={t.name}>
                {t.display_name ?? t.name} (v{t.version})
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="gen-vars" className="block text-xs text-muted-foreground mb-1">
            Generator Variables (key=val1,val2 per line)
          </label>
          <textarea
            id="gen-vars"
            value={genVarsText}
            onChange={e => setGenVarsText(e.target.value)}
            rows={4}
            className="w-full px-3 py-1.5 text-sm bg-muted/30 border border-border rounded text-foreground font-mono"
            placeholder={`process_name=auth,cache,db`}
          />
        </div>

        <div className="flex gap-2 justify-end pt-2">
          <Button type="button" size="sm" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="submit"
            size="sm"
            disabled={!name || !templateSloName || createMutation.isPending}
          >
            {createMutation.isPending ? 'Generating…' : 'Generate'}
          </Button>
        </div>
      </form>
    </div>
  )
}
