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
      <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
        Step 1 — Identity
      </h3>

      <div>
        <label htmlFor="slo-name" className="block text-xs text-muted-foreground mb-1">
          Name
        </label>
        <Input
          id="slo-name"
          value={data.name}
          onChange={(e) => update('name', e.target.value)}
          placeholder="my-slo-definition"
          disabled={nameReadOnly}
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
        <Input
          id="slo-notes"
          value={data.notes}
          onChange={(e) => update('notes', e.target.value)}
          placeholder="Optional notes"
        />
      </div>
    </div>
  )
}
