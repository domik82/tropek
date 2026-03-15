// src/pages/AssetsPage.tsx
import { useState } from 'react'
import { useAssetGroups } from '@/features/assets/hooks'
import { AssetGroupCard } from '@/features/assets/components/AssetGroupCard'
import { AssetFilter } from '@/features/assets/components/AssetFilter'
import { ColourLegend } from '@/features/assets/components/ColourLegend'
import { DEFAULT_OS_COLOUR_MAP } from '@/lib/theme'

export function AssetsPage() {
  const { data: tree, isLoading, isError } = useAssetGroups()
  const [query, setQuery] = useState('')
  const [colourMap, setColourMap] = useState<Record<string, string>>(DEFAULT_OS_COLOUR_MAP)
  const [forceExpanded, setForceExpanded] = useState<boolean | undefined>(undefined)

  if (isLoading) return <p className="p-6 text-gray-400">Loading...</p>
  if (isError || !tree) return <p className="p-6">Failed to load data.</p>

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-xl font-semibold">Asset Registry</h1>
      <ColourLegend
        colourMap={colourMap}
        onColourChange={(os, colour) => setColourMap(prev => ({ ...prev, [os]: colour }))}
      />
      <AssetFilter
        query={query}
        onQueryChange={setQuery}
        onExpandAll={() => setForceExpanded(true)}
        onCollapseAll={() => setForceExpanded(false)}
      />
      {tree.top_level.map(group => (
        <AssetGroupCard
          key={group.id}
          group={group}
          tree={tree}
          filterQuery={query}
          colourMap={colourMap}
          forceExpanded={forceExpanded}
        />
      ))}
    </div>
  )
}
