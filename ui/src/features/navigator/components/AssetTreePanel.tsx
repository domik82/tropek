interface Props {
  selectedGroup?: string
  selectedAsset?: string
  onSelectGroup: (name: string) => void
  onSelectAsset: (name: string) => void
}
export function AssetTreePanel(_props: Props) {
  return <div className="p-3 text-muted-foreground text-xs">Tree loading…</div>
}
