import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { trackTooltip, releaseTooltip } from './tooltipWatchdog'
import type { TooltipChart } from './tooltipWatchdog'

interface FakeChart extends TooltipChart {
  dispatchAction: ReturnType<typeof vi.fn<(payload: { type: string }) => void>>
}

function makeChart(disposed = false): FakeChart {
  return {
    dispatchAction: vi.fn<(payload: { type: string }) => void>(),
    isDisposed: () => disposed,
  }
}

function makeContainer(): HTMLElement {
  const container = document.createElement('div')
  document.body.appendChild(container)
  return container
}

function movePointerOver(element: Element | Document): void {
  element.dispatchEvent(new MouseEvent('pointermove', { bubbles: true }))
}

function hideActions(chart: FakeChart): string[] {
  return chart.dispatchAction.mock.calls.map(call => (call[0] as { type: string }).type)
}

describe('tooltipWatchdog', () => {
  let chartA: FakeChart
  let chartB: FakeChart
  let containerA: HTMLElement
  let containerB: HTMLElement
  let outside: HTMLElement

  beforeEach(() => {
    chartA = makeChart()
    chartB = makeChart()
    containerA = makeContainer()
    containerB = makeContainer()
    outside = makeContainer()
  })

  afterEach(() => {
    releaseTooltip(chartA)
    releaseTooltip(chartB)
    document.body.innerHTML = ''
  })

  it('hides the previous chart tooltip when another chart shows one', () => {
    trackTooltip(chartA, containerA)
    trackTooltip(chartB, containerB)

    expect(hideActions(chartA)).toEqual(['hideTip', 'downplay'])
    expect(chartB.dispatchAction).not.toHaveBeenCalled()
  })

  it('hides the tooltip when the pointer moves outside the owning container', () => {
    trackTooltip(chartA, containerA)
    movePointerOver(outside)

    expect(hideActions(chartA)).toEqual(['hideTip', 'downplay'])
  })

  it('keeps the tooltip while the pointer moves inside the owning container', () => {
    const cell = document.createElement('span')
    containerA.appendChild(cell)
    trackTooltip(chartA, containerA)
    movePointerOver(cell)

    expect(chartA.dispatchAction).not.toHaveBeenCalled()
  })

  it('hides the tooltip when the window loses focus', () => {
    trackTooltip(chartA, containerA)
    window.dispatchEvent(new Event('blur'))

    expect(hideActions(chartA)).toEqual(['hideTip', 'downplay'])
  })

  it('hides the tooltip when the pointer leaves the viewport', () => {
    trackTooltip(chartA, containerA)
    document.documentElement.dispatchEvent(new MouseEvent('mouseleave'))

    expect(hideActions(chartA)).toEqual(['hideTip', 'downplay'])
  })

  it('hides only once for repeated outside movement', () => {
    trackTooltip(chartA, containerA)
    movePointerOver(outside)
    movePointerOver(outside)

    expect(hideActions(chartA)).toEqual(['hideTip', 'downplay'])
  })

  it('re-tracking the same chart does not hide it', () => {
    trackTooltip(chartA, containerA)
    trackTooltip(chartA, containerA)

    expect(chartA.dispatchAction).not.toHaveBeenCalled()
  })

  it('does not dispatch to a disposed chart', () => {
    const disposedChart = makeChart(true)
    trackTooltip(disposedChart, containerA)
    movePointerOver(outside)

    expect(disposedChart.dispatchAction).not.toHaveBeenCalled()
  })

  it('releaseTooltip stops tracking without dispatching (unmount path)', () => {
    trackTooltip(chartA, containerA)
    releaseTooltip(chartA)
    movePointerOver(outside)

    expect(chartA.dispatchAction).not.toHaveBeenCalled()
  })

  it('releaseTooltip for a non-active chart leaves the active one tracked', () => {
    trackTooltip(chartA, containerA)
    releaseTooltip(chartB)
    movePointerOver(outside)

    expect(hideActions(chartA)).toEqual(['hideTip', 'downplay'])
  })
})
