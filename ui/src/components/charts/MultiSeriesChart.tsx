// ui/src/components/charts/MultiSeriesChart.tsx
//
// Renders multiple time-series lines on a shared X axis.
// Each series supplies its own colour and display name.
// Missing timestamps within a series are mapped to null — ECharts
// will leave a gap rather than interpolate.

import ReactECharts from 'echarts-for-react'
import { useMemo } from 'react'
import { useTheme } from '@/lib/theme-context'
import { CHART_THEME } from '@/lib/theme'
import { fmtSlot } from '@/lib/format'

// ── Props ─────────────────────────────────────────────────────────────────────

export interface MultiSeriesChartProps {
  series: Array<{
    metric: string
    displayName: string
    color: string
    data: Array<{ timestamp: string; value: number }>
  }>
  yAxisLabel?: string
  yAxisMin?: number
  yAxisMax?: number
  chartType?: 'line' | 'bar'
  stacked?: boolean
  height?: number | string
}

// ── Component ─────────────────────────────────────────────────────────────────

export function MultiSeriesChart({
  series,
  yAxisLabel,
  yAxisMin,
  yAxisMax,
  chartType = 'line',
  stacked = false,
  height = 300,
}: MultiSeriesChartProps) {
  const { theme } = useTheme()
  const ct = CHART_THEME[theme]

  // Build sorted union of all timestamps across all series
  const allTimestamps = useMemo(() => {
    const seen = new Set<string>()
    for (const s of series) {
      for (const pt of s.data) {
        seen.add(pt.timestamp)
      }
    }
    return Array.from(seen).sort()
  }, [series])

  const option = useMemo(() => {
    // For each series, build a value array aligned to allTimestamps
    const eChartsSeries = series.map(s => {
      const lookup = new Map<string, number>()
      for (const pt of s.data) {
        lookup.set(pt.timestamp, pt.value)
      }

      const data = allTimestamps.map(ts => {
        const v = lookup.get(ts)
        return v !== undefined ? v : null
      })

      return {
        name: s.displayName,
        type: chartType,
        data,
        lineStyle: { color: s.color, width: 1.5 },
        itemStyle: { color: s.color },
        symbol: 'circle',
        symbolSize: 4,
        connectNulls: false,
        ...(stacked ? { stack: 'total', areaStyle: { opacity: 0.3 } } : {}),
      }
    })

    const xAxisLabels = allTimestamps.map(fmtSlot)

    return {
      backgroundColor: 'transparent',
      animation: false,
      grid: { top: 16, bottom: 52, left: 56, right: 16 },
      tooltip: {
        trigger: 'axis' as const,
        backgroundColor: ct.bg,
        borderColor: ct.border,
        textStyle: { color: ct.axisLabel, fontSize: 13 },
        extraCssText:
          series.length > 10
            ? 'max-height:300px;overflow-y:auto;'
            : undefined,
        formatter: (
          params: Array<{
            seriesName: string
            value: number | null
            color: string
            axisValueLabel: string
          }>,
        ): string => {
          if (!params || params.length === 0) return ''
          const label = params[0].axisValueLabel
          const rows = params
            .map(
              p =>
                `<span style="color:${p.color}">●</span> ${p.seriesName}: ${p.value !== null && p.value !== undefined ? p.value : '—'}`,
            )
            .join('<br/>')
          const inner = `<b>${label}</b><br/>${rows}`
          return `<div style="max-height:300px;overflow-y:auto">${inner}</div>`
        },
      },
      xAxis: {
        type: 'category' as const,
        data: xAxisLabels,
        axisLabel: { rotate: 45, fontSize: 12, color: ct.axisLabel },
        axisLine: { lineStyle: { color: ct.grid } },
        splitLine: { show: false },
      },
      yAxis: {
        type: 'value' as const,
        name: yAxisLabel,
        min: yAxisMin,
        max: yAxisMax,
        axisLabel: { fontSize: 12, color: ct.axisLabel },
        axisLine: { lineStyle: { color: ct.grid } },
        splitLine: { lineStyle: { color: ct.grid } },
      },
      series: eChartsSeries,
    }
  }, [series, allTimestamps, ct, yAxisLabel, yAxisMin, yAxisMax, chartType, stacked])

  return (
    <ReactECharts
      option={option}
      style={{ height }}
      opts={{ renderer: 'svg' }}
      notMerge
    />
  )
}
