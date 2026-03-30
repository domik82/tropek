import { Input } from '@/components/ui/input'

interface Props {
  reason: string
  onReasonChange: (v: string) => void
  author: string
  onAuthorChange: (v: string) => void
}

export function ReasonAuthorFields({ reason, onReasonChange, author, onAuthorChange }: Props) {
  return (
    <>
      <Input value={reason} onChange={e => onReasonChange(e.target.value)} placeholder="Reason…" />
      <Input
        value={author}
        onChange={e => onAuthorChange(e.target.value)}
        placeholder="Author"
        autoComplete="name"
      />
    </>
  )
}
