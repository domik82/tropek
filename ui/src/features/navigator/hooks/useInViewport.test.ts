// ui/src/features/navigator/hooks/useInViewport.test.ts
import { test, beforeEach, expect, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useInViewport } from './useInViewport'

class MockObserver {
  static instances: MockObserver[] = []
  callback: IntersectionObserverCallback
  options?: IntersectionObserverInit
  disconnectCount = 0
  constructor(callback: IntersectionObserverCallback, options?: IntersectionObserverInit) {
    this.callback = callback
    this.options = options
    MockObserver.instances.push(this)
  }
  observe() {}
  disconnect() {
    this.disconnectCount += 1
  }
  trigger(isIntersecting: boolean) {
    this.callback([{ isIntersecting } as IntersectionObserverEntry], this as unknown as IntersectionObserver)
  }
}

beforeEach(() => {
  MockObserver.instances = []
  vi.stubGlobal('IntersectionObserver', MockObserver)
})

test('inView flips to true once the element intersects and stays true', () => {
  const { result } = renderHook(() => useInViewport<HTMLDivElement>())
  act(() => {
    result.current.ref(document.createElement('div'))
  })
  expect(result.current.inView).toBe(false)
  act(() => {
    MockObserver.instances[0].trigger(true)
  })
  expect(result.current.inView).toBe(true)
  act(() => {
    MockObserver.instances[0].trigger(false)
  })
  expect(result.current.inView).toBe(true) // once: true keeps it latched
})

test('once-mode disconnects the observer after the first intersection', () => {
  const { result } = renderHook(() => useInViewport<HTMLDivElement>())
  act(() => {
    result.current.ref(document.createElement('div'))
  })
  expect(MockObserver.instances[0].disconnectCount).toBe(0)
  act(() => {
    MockObserver.instances[0].trigger(true)
  })
  // The one-shot latch must release the observer so it stops observing.
  expect(MockObserver.instances[0].disconnectCount).toBe(1)
})

test('disconnects the observer when the node detaches (unmount)', () => {
  const { result } = renderHook(() => useInViewport<HTMLDivElement>())
  act(() => {
    result.current.ref(document.createElement('div'))
  })
  const observer = MockObserver.instances[0]
  // Never intersected, so still observing. On unmount React invokes the
  // callback ref with null — that must disconnect the live observer, not leak it.
  expect(observer.disconnectCount).toBe(0)
  act(() => {
    result.current.ref(null)
  })
  expect(observer.disconnectCount).toBe(1)
})

test('forwards rootMargin to the IntersectionObserver', () => {
  const { result } = renderHook(() => useInViewport<HTMLDivElement>({ rootMargin: '200px' }))
  act(() => {
    result.current.ref(document.createElement('div'))
  })
  expect(MockObserver.instances[0].options).toEqual({ rootMargin: '200px' })
})
