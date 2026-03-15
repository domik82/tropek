interface Props { groupName: string }
export function GroupPanel({ groupName }: Props) {
  return <div className="p-6 text-muted-foreground text-sm">Group: {groupName}</div>
}
