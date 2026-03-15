// src/features/evaluations/components/AnnotationCell.tsx
import type { Annotation } from '../types'

interface Props {
  annotation?: Annotation
  count?: number
}

export function AnnotationCell({ annotation, count }: Props) {
  if (!annotation) return <span className="text-gray-500">—</span>
  return (
    <div className="text-sm">
      <p className="line-clamp-2 text-gray-300">{annotation.content}</p>
      {count && count > 1 && (
        <span className="text-xs text-gray-500 ml-1">+{count - 1} more</span>
      )}
    </div>
  )
}
