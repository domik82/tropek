// ui/src/features/navigator/hooks/useInViewport.ts
import { useCallback, useRef, useState } from 'react'

/**
 * Track whether an element has entered the viewport. With `once` (default) the
 * flag latches true on first intersection so a lazily-loaded section does not
 * unload when scrolled away. Used to defer per-SLO trend fetches until visible.
 *
 * `rootMargin` (an IntersectionObserver margin string, e.g. `"200px"`) grows the
 * observed area so a section starts loading shortly before it scrolls into view.
 */
export function useInViewport<T extends Element>(options?: { once?: boolean; rootMargin?: string }) {
  const once = options?.once ?? true
  const rootMargin = options?.rootMargin
  const [inView, setInView] = useState(false)
  const observerRef = useRef<IntersectionObserver | null>(null)

  const ref = useCallback(
    (node: T | null) => {
      observerRef.current?.disconnect()
      observerRef.current = null
      if (!node) return
      const observer = new IntersectionObserver(
        entries => {
          const isIntersecting = entries.some(entry => entry.isIntersecting)
          if (isIntersecting) {
            setInView(true)
            if (once) {
              observer.disconnect()
              observerRef.current = null
            }
          } else if (!once) {
            setInView(false)
          }
        },
        rootMargin ? { rootMargin } : undefined,
      )
      observer.observe(node)
      observerRef.current = observer
    },
    [once, rootMargin],
  )

  return { ref, inView }
}
