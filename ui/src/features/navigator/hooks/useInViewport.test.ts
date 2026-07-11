// ui/src/features/navigator/hooks/useInViewport.test.ts
import { test, beforeEach, expect, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useInViewport } from './useInViewport'

class MockObserver {
  static instances: MockObserver[] = []
  callback: IntersectionObserverCallback
  constructor(callback: IntersectionObserverCallback) {
    this.callback = callback
    MockObserver.instances.push(this)
  }
  observe() {}
  disconnect() {}
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
