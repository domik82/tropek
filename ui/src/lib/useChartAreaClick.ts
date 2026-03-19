// ui/src/lib/useChartAreaClick.ts
//
// Makes the entire ECharts grid area clickable — a React onClick on a wrapper
// div converts the click position to the nearest x-axis category index via
// the chart instance's convertFromPixel. No dependency on zrender events.
//
// Usage:
//   const { chartRef, onContainerClick } = useChartAreaClick(callback, dataLength)
//   <div onClick={onContainerClick}>
//     <ReactECharts ref={chartRef} ... />
//   </div>
import { useCallback, useRef } from 'react'
import type ReactECharts from 'echarts-for-react'
import type { MouseEvent } from 'react'

export function useChartAreaClick(
  onClickIndex: ((index: number) => void) | undefined,
  dataLength: number,
) {
  const chartRef = useRef<ReactECharts>(null)

  const onContainerClick = useCallback(
    (e: MouseEvent<HTMLDivElement>) => {
      if (!onClickIndex || dataLength === 0) return
      const instance = chartRef.current?.getEchartsInstance()
      if (!instance) return

      const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
      const point = [e.clientX - rect.left, e.clientY - rect.top] as [number, number]
      if (!instance.containPixel('grid', point)) return

      const [xVal] = instance.convertFromPixel({ seriesIndex: 0 }, point)
      const idx = Math.max(0, Math.min(Math.round(xVal), dataLength - 1))
      onClickIndex(idx)
    },
    [onClickIndex, dataLength],
  )

  return { chartRef, onContainerClick }
}
