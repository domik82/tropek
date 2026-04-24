import { useRef, useState, useEffect, type ReactNode } from 'react'

interface Props {
  estimatedHeight: number
  rootMargin?: string
  children: ReactNode
}

export function LazyHeatmap({
  estimatedHeight,
  rootMargin = '400px 0px',
  children,
}: Props) {
  const ref = useRef<HTMLDivElement>(null)
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    const el = ref.current
    if (!el || mounted) return

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setMounted(true)
          observer.disconnect()
        }
      },
      { rootMargin },
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [mounted, rootMargin])

  return (
    <div ref={ref} style={mounted ? undefined : { minHeight: estimatedHeight }}>
      {mounted ? children : null}
    </div>
  )
}
