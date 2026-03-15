interface Props { assetName: string }
export function AssetPanel({ assetName }: Props) {
  return <div className="p-6 text-muted-foreground text-sm">Asset: {assetName}</div>
}
