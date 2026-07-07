// ui/src/components/charts/tooltipWatchdog.ts
//
// Page-level singleton that keeps at most ONE ECharts tooltip visible across
// all chart instances, and force-hides it once the pointer is no longer over
// the chart that owns it.
//
// Why this exists: views like the asset heatmap stack many independent
// ECharts instances. ECharts hides an item tooltip only from its own
// container's pointerout/globalout events, but Chrome skips those boundary
// events during fast mouse movement across stacked charts, leaving orphaned
// tooltips behind (and no code path ever hides another chart's tooltip).
// `pointermove` is not a boundary event and is never skipped while the
// pointer is over the page, so a document-level watchdog is reliable where
// per-container listeners are not.

export interface TooltipChart {
  dispatchAction: (payload: { type: string }) => void
  isDisposed: () => boolean
}

interface ActiveTooltip {
  chart: TooltipChart
  container: HTMLElement
}

let active: ActiveTooltip | null = null

function hideActiveTooltip(): void {
  if (!active) return
  const { chart } = active
  active = null
  detachListeners()
  if (!chart.isDisposed()) {
    chart.dispatchAction({ type: 'hideTip' })
    chart.dispatchAction({ type: 'downplay' })
  }
}

function handlePointerMove(event: Event): void {
  if (!active) return
  const target = event.target
  if (!(target instanceof Node) || !active.container.contains(target)) {
    hideActiveTooltip()
  }
}

function handlePointerGone(): void {
  hideActiveTooltip()
}

let listenersAttached = false

function attachListeners(): void {
  if (listenersAttached) return
  listenersAttached = true
  document.addEventListener('pointermove', handlePointerMove, { capture: true, passive: true })
  document.documentElement.addEventListener('mouseleave', handlePointerGone)
  window.addEventListener('blur', handlePointerGone)
}

function detachListeners(): void {
  if (!listenersAttached) return
  listenersAttached = false
  document.removeEventListener('pointermove', handlePointerMove, { capture: true })
  document.documentElement.removeEventListener('mouseleave', handlePointerGone)
  window.removeEventListener('blur', handlePointerGone)
}

/**
 * Record that `chart` is currently showing a tooltip inside `container`.
 * Call on every ECharts `showtip` event. Any other chart's tooltip is
 * hidden immediately so only one tooltip exists page-wide.
 */
export function trackTooltip(chart: TooltipChart, container: HTMLElement): void {
  if (active && active.chart !== chart) {
    hideActiveTooltip()
  }
  active = { chart, container }
  attachListeners()
}

/**
 * Stop tracking `chart` without dispatching anything (unmount path — the
 * tooltip DOM disappears with the chart, there is nothing left to hide).
 */
export function releaseTooltip(chart: TooltipChart): void {
  if (active && active.chart === chart) {
    active = null
    detachListeners()
  }
}
