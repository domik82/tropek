// src/features/slos/components/SloYamlViewer.tsx
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { useState } from 'react'

interface Props {
  yaml: string
}

export function SloYamlViewer({ yaml }: Props) {
  const [open, setOpen] = useState(false)

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger className="flex items-center gap-2 text-xs text-gray-500 uppercase tracking-wider hover:text-gray-300 transition-colors">
        <span>{open ? '▼' : '▶'}</span>
        Raw YAML {open ? '' : '· click to expand'}
      </CollapsibleTrigger>
      <CollapsibleContent>
        <pre className="mt-2 p-4 bg-gray-900 rounded border border-gray-700 text-xs font-mono text-gray-300 overflow-x-auto whitespace-pre-wrap">
          {yaml}
        </pre>
      </CollapsibleContent>
    </Collapsible>
  )
}
