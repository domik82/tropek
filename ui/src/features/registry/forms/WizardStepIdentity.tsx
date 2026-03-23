import { Input } from '@/components/ui/input'

export interface IdentityData {
  name: string
  display_name: string
  author: string
  notes: string
}

interface WizardStepIdentityProps {
  data: IdentityData
  onChange: (data: IdentityData) => void
  nameReadOnly?: boolean
}

export function WizardStepIdentity({ data, onChange, nameReadOnly }: WizardStepIdentityProps) {
  function update(field: keyof IdentityData, value: string) {
    onChange({ ...data, [field]: value })
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 mb-3">
        <span className="inline-flex items-center justify-center size-5 rounded-full bg-primary/15 text-primary text-[10px] font-bold">1</span>
        <h3 className="text-sm font-semibold text-foreground">Identity</h3>
      </div>

      <div>
        <label htmlFor="slo-name" className="block text-xs text-muted-foreground mb-1">
          Name
        </label>
        <Input
          id="slo-name"
          value={data.name}
          onChange={(e) => update('name', e.target.value)}
          placeholder="my-slo-definition"
          readOnly={nameReadOnly}
        />
      </div>

      <div>
        <label htmlFor="slo-display-name" className="block text-xs text-muted-foreground mb-1">
          Display Name
        </label>
        <Input
          id="slo-display-name"
          value={data.display_name}
          onChange={(e) => update('display_name', e.target.value)}
          placeholder="My SLO Definition"
        />
      </div>

      <div>
        <label htmlFor="slo-author" className="block text-xs text-muted-foreground mb-1">
          Author
        </label>
        <Input
          id="slo-author"
          value={data.author}
          onChange={(e) => update('author', e.target.value)}
          placeholder="your-name"
        />
      </div>

      <div>
        <label htmlFor="slo-notes" className="block text-xs text-muted-foreground mb-1">
          Notes
        </label>
        <textarea
          id="slo-notes"
          className="flex w-full rounded-lg border border-input bg-transparent px-2.5 py-2 text-sm placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
          rows={3}
          value={data.notes}
          onChange={(e) => update('notes', e.target.value)}
          placeholder="Optional notes about this SLO definition"
        />
      </div>
    </div>
  )
}
