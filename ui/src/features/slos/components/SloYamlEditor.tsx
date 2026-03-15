// src/features/slos/components/SloYamlEditor.tsx
import { useState } from 'react'
import { useSloValidation } from '../hooks'
import type { SloDefinition } from '../types'

interface Props {
  slo: SloDefinition
  onCancel: () => void
  onSaved: () => void
}

export function SloYamlEditor({ slo, onCancel, onSaved }: Props) {
  const [yaml, setYaml] = useState(slo.slo_yaml ?? '')
  const validation = useSloValidation()

  function handleSave() {
    validation.mutate(yaml, {
      onSuccess: (result) => {
        if (result.valid) onSaved()
      },
    })
  }

  return (
    <div className="space-y-3">
      <textarea
        value={yaml}
        onChange={e => setYaml(e.target.value)}
        className="w-full h-96 bg-slate-900 border border-slate-700 rounded-lg p-3 font-mono text-xs text-slate-200 resize-y focus:outline-none focus:border-indigo-500"
        spellCheck={false}
      />
      {validation.data && !validation.data.valid && (
        <div className="bg-red-900/20 border border-red-700/40 rounded p-3 text-xs space-y-1">
          <p className="text-red-400 font-semibold">Validation errors:</p>
          {validation.data.errors.map((e, i) => (
            <p key={i} className="text-red-300">{e.field}: {e.message}</p>
          ))}
        </div>
      )}
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="px-3 py-1.5 text-xs rounded border border-slate-600 text-slate-400 hover:text-slate-200 transition-colors"
        >
          Cancel
        </button>
        <button
          onClick={handleSave}
          disabled={validation.isPending}
          className="px-3 py-1.5 text-xs font-medium rounded bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {validation.isPending ? 'Validating…' : 'Validate & Save'}
        </button>
      </div>
    </div>
  )
}
