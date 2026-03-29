import { useState, useRef, useEffect } from 'react'
import { Input } from '@/components/ui/input'

interface Props {
  currentName: string
  onSave: (newName: string) => void
  onCancel: () => void
}

export function AssetTreeInlineRename({ currentName, onSave, onCancel }: Props) {
  const [value, setValue] = useState(currentName)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    inputRef.current?.select()
  }, [])

  const handleSave = () => {
    const trimmed = value.trim()
    if (trimmed && trimmed !== currentName) {
      onSave(trimmed)
    } else {
      onCancel()
    }
  }

  return (
    <Input
      ref={inputRef}
      type="text"
      value={value}
      onChange={e => setValue(e.target.value)}
      onKeyDown={e => {
        if (e.key === 'Enter') handleSave()
        if (e.key === 'Escape') onCancel()
      }}
      onBlur={handleSave}
      autoFocus
      className="h-auto px-1 py-0.5"
    />
  )
}
