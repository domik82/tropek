import { useRef, useState, useEffect, type ReactNode } from 'react'

export function DeferredWhenOffscreen({
  selectedColumn,
  deferredSelectedColumn,
  children,
}: {
  selectedColumn: number | undefined
  deferredSelectedColumn: number | undefined
  children: (effectiveColumn: number | undefined) => ReactNode
}) {
  const divRef = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const element = divRef.current
    if (!element) return
    const observer = new IntersectionObserver(
      ([entry]) => setVisible(entry.isIntersecting),
      { threshold: 0 },
    )
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  return <div ref={divRef}>{children(visible ? selectedColumn : deferredSelectedColumn)}</div>
}
