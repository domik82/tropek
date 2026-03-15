// src/features/slos/components/SloYamlUpload.tsx
import { useRef, useState } from 'react'
import { parseSloYaml, type ParsedSloYaml, type ParsedObjective } from '@/lib/parseSloYaml'
import { useUploadSlo } from '../hooks'

interface Props {
  onCancel: () => void
  onSaved: () => void
}

function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-slate-500 w-40 shrink-0">{label}</span>
      <span className="text-xs text-slate-200 font-mono">{value || '—'}</span>
    </div>
  )
}

function ObjectivesPreviewTable({ objectives }: { objectives: ParsedObjective[] }) {
  return (
    <div className="overflow-x-auto rounded border border-slate-700">
      <table className="w-full text-xs">
        <thead className="text-slate-400 uppercase bg-slate-800/60 border-b border-slate-700">
          <tr>
            <th className="px-2 py-2 text-center w-6 text-cyan-500/70">◆</th>
            <th className="text-left px-3 py-2">Indicator</th>
            <th className="text-left px-3 py-2">Display Name</th>
            <th className="text-center px-3 py-2">Pass</th>
            <th className="text-center px-3 py-2">Warning</th>
            <th className="text-center px-3 py-2 w-16">Weight</th>
            <th className="text-center px-3 py-2 w-24">Group</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800">
          {objectives.map((obj, i) => (
            <tr key={i} className="hover:bg-slate-800/40">
              <td className="px-2 py-2 text-center">
                {obj.key_sli
                  ? <span className="text-cyan-400" title="Key SLI">◆</span>
                  : <span className="text-slate-700">—</span>
                }
              </td>
              <td className="px-3 py-2 font-mono text-[#7dc540]">{obj.sli_name}</td>
              <td className="px-3 py-2 text-slate-300">{obj.display_name || '—'}</td>
              <td className="px-3 py-2 text-center text-[#7dc540]">{obj.pass.join(', ') || '—'}</td>
              <td className="px-3 py-2 text-center text-[#e6be00]">{obj.warning.join(', ') || '—'}</td>
              <td className="px-3 py-2 text-center text-slate-400">{obj.weight}</td>
              <td className="px-3 py-2 text-center">
                {obj.tab_group
                  ? <span className="bg-slate-700/60 text-slate-300 px-1.5 py-0.5 rounded">{obj.tab_group}</span>
                  : <span className="text-slate-600">—</span>
                }
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function SloYamlUpload({ onCancel, onSaved }: Props) {
  const [yaml, setYaml] = useState<string | null>(null)
  const [parsed, setParsed] = useState<ParsedSloYaml | null>(null)
  const [parseError, setParseError] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const upload = useUploadSlo()

  function readFile(file: File) {
    const reader = new FileReader()
    reader.onload = e => {
      const text = e.target?.result as string
      setYaml(text)
      upload.reset()
      const result = parseSloYaml(text)
      if (result) {
        setParsed(result)
        setParseError(null)
      } else {
        setParsed(null)
        setParseError('Could not parse YAML — check the format is tropek/v1 SLO')
      }
    }
    reader.readAsText(file)
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) readFile(file)
  }

  function handleSave() {
    if (!yaml || !parsed) return
    upload.mutate(
      { name: parsed.metadata.name, slo_yaml: yaml },
      { onSuccess: () => onSaved() }
    )
  }

  return (
    <div className="space-y-4">
      {/* Drop zone */}
      <div
        onDragOver={e => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
          dragOver ? 'border-indigo-500 bg-indigo-500/10' : 'border-slate-600 hover:border-slate-400'
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".yaml,.yml"
          className="hidden"
          onChange={e => { const f = e.target.files?.[0]; if (f) readFile(f) }}
        />
        <p className="text-2xl mb-2 text-slate-400">↑</p>
        <p className="text-sm text-slate-300">
          Drop SLO YAML file here or <span className="text-indigo-400">browse</span>
        </p>
        <p className="text-xs text-slate-500 mt-1">tropek/v1 SLO format</p>
        {yaml && !parseError && (
          <p className="text-xs text-[#7dc540] mt-2">File loaded — parsed successfully</p>
        )}
      </div>

      {parseError && (
        <div className="bg-red-900/20 border border-red-700/40 rounded p-3 text-xs text-red-300">
          {parseError}
        </div>
      )}

      {/* Structured preview */}
      {parsed && (
        <div className="space-y-4">
          {/* Metadata section */}
          <div className="bg-[#111827] border border-slate-700 rounded-xl p-4 space-y-2">
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Metadata</h3>
            <MetaRow label="api_version" value={parsed.api_version} />
            <MetaRow label="kind" value={parsed.kind} />
            <MetaRow label="name" value={parsed.metadata.name} />
            {Object.entries(parsed.metadata.labels).map(([k, v]) => (
              <MetaRow key={k} label={`labels.${k}`} value={v} />
            ))}
          </div>

          {/* Comparison section */}
          {Object.keys(parsed.spec.comparison).length > 0 && (
            <div className="bg-[#111827] border border-slate-700 rounded-xl p-4 space-y-2">
              <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Comparison Settings</h3>
              {Object.entries(parsed.spec.comparison).map(([k, v]) => (
                <MetaRow key={k} label={k.replace(/_/g, ' ')} value={String(v)} />
              ))}
            </div>
          )}

          {/* Score thresholds */}
          {(parsed.spec.total_score.pass || parsed.spec.total_score.warning) && (
            <div className="flex flex-wrap gap-6 text-sm text-slate-400 px-1">
              {parsed.spec.total_score.pass && (
                <span>Total pass: <strong className="text-[#7dc540]">{parsed.spec.total_score.pass}</strong></span>
              )}
              {parsed.spec.total_score.warning && (
                <span>Total warning: <strong className="text-[#e6be00]">{parsed.spec.total_score.warning}</strong></span>
              )}
            </div>
          )}

          {/* Objectives */}
          <div className="space-y-2">
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wide">
              Objectives <span className="text-slate-600 normal-case font-normal">({parsed.spec.objectives.length})</span>
            </h3>
            <ObjectivesPreviewTable objectives={parsed.spec.objectives} />
          </div>
        </div>
      )}

      {upload.isError && (
        <div className="bg-red-900/20 border border-red-700/40 rounded p-3 text-xs text-red-300">
          Failed to save — please try again
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
          disabled={!parsed || upload.isPending}
          className="px-3 py-1.5 text-xs font-medium rounded bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {upload.isPending ? 'Saving…' : 'Save to Registry'}
        </button>
      </div>
    </div>
  )
}
