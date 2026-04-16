// ui/src/features/meta_timeline/ui-types.ts
//
// Types used only by components (prop shapes). Not re-exported from index.ts.

export interface MetaTimelineSectionProps {
  assetId: string
  focusEval: { id: string; periodEnd: Date }
}

export interface CollapsedStripProps {
  itemCount: number
  expanded: boolean
  onToggle: () => void
}
