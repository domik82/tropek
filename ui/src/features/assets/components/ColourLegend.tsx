// src/features/assets/components/ColourLegend.tsx
import { DEFAULT_OS_COLOUR_MAP } from '@/lib/theme'

interface Props {
  colourMap: Record<string, string>
  onColourChange: (os: string, colour: string) => void
}

export function ColourLegend({ colourMap, onColourChange }: Props) {
  const entries = Object.entries({ ...DEFAULT_OS_COLOUR_MAP, ...colourMap })

  return (
    <div className="flex flex-wrap gap-3 mb-4">
      {entries.map(([os, colour]) => (
        <label key={os} className="flex items-center gap-2 cursor-pointer text-sm">
          <input
            type="color"
            value={colour}
            onChange={e => onColourChange(os, e.target.value)}
            className="w-6 h-6 rounded cursor-pointer border-0"
          />
          <span className="text-slate-300">{os}</span>
        </label>
      ))}
    </div>
  )
}
