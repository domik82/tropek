// src/features/evaluations/components/AnnotationCell.tsx
import type { Annotation } from '../domain'

interface Props {
  annotation?: Annotation
  count?: number
}

export function AnnotationCell({ annotation, count }: Props) {
  if (!annotation) return <span className="text-muted-foreground">—</span>
  return (
    <div className="text-sm">
      <p className="line-clamp-2 text-foreground">{annotation.content}</p>
      {count && count > 1 && (
        <span className="text-xs text-muted-foreground ml-1">+{count - 1} more</span>
      )}
    </div>
  )
}
