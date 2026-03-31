import { useState } from 'react'

export function useReasonAuthor() {
  const [reason, setReason] = useState('')
  const [author, setAuthor] = useState('')
  const canConfirm = !!reason.trim() && !!author.trim()
  return { reason, setReason, author, setAuthor, canConfirm }
}
