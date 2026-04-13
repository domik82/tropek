// ui/src/features/navigator/components/GroupScoreChart.tsx
import ReactECharts from 'echarts-for-react'
import { useMemo, useState } from 'react'
import { useTheme } from '@/lib/theme-context'
import { RESULT_COLOUR, CHART_THEME } from '@/lib/theme'
import { fmtSlot } from '@/lib/format'
import { buildGroupScoreData } from '../utils'
import type { Evaluation } from '@/features/evaluations'

interface Props {
  evaluations: Evaluation[]
  assetDisplayNames?: Map<string, string>
}

export function GroupScoreChart({ evaluations, assetDisplayNames }: Props) {
  const { theme } = useTheme()
  const colours = RESULT_COLOUR[theme]
  const ct = CHART_THEME[theme]
  const [normalized, setNormalized] = useState(false)

  const slotData = useMemo(() => buildGroupScoreData(evaluations), [evaluations])
  const assetNames = Array.from(new Set(evaluations.map(e => e.assetSnapshot.name))).sort()
  const slots = slotData.map(d => d.slot)

  const displayNameMap = useMemo(() => {
    const map = new Map<string, string>()
    for (const e of evaluations) {
      if (!map.has(e.assetSnapshot.name)) {
        const dn = e.assetSnapshot.displayName ?? assetDisplayNames?.get(e.assetSnapshot.name)
        if (dn) map.set(e.assetSnapshot.name, dn)
      }
    }
    return map
  }, [evaluations, assetDisplayNames])

  // One series per asset — stacked bars
  const series = assetNames.map(assetName => ({
    name: displayNameMap.get(assetName) ?? assetName,
    type: 'bar' as const,
    stack: 'score',
    data: slotData.map(slotRow => {
      const ap = slotRow.assets.find(a => a.assetName === assetName)
      if (!ap) return { value: 0, itemStyle: { color: ct.bg } }
      const value = normalized
        ? (ap.score / 100) * (100 / assetNames.length)
        : ap.score
      return {
        value: +value.toFixed(1),
        itemStyle: { color: colours[ap.result as keyof typeof colours] ?? ct.bg },
        // Store original data for tooltip
        assetName: ap.assetName,
        score: ap.score,
        result: ap.result,
      }
    }),
  }))

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis' as const,
      axisPointer: { type: 'shadow' as const },
      backgroundColor: ct.bg,
      borderColor: ct.border,
      textStyle: { color: ct.axisLabel },
      formatter: (params: Array<{ seriesName: string; data: { score?: number; result?: string; value: number } }>) => {
        const lines = params
          .filter(p => (p.data.score ?? p.data.value) > 0)
          .map(p => {
            const rc = colours[(p.data.result as keyof typeof colours) ?? 'pass'] ?? '#ccc'
            return `<span style="color:${rc}">● ${p.seriesName}: ${p.data.score ?? p.data.value}%</span>`
          })
        return lines.join('<br/>')
      },
    },
    xAxis: {
      type: 'category' as const,
      data: slots.map(fmtSlot),
      axisLabel: { rotate: 45, fontSize: 11, color: ct.axisLabel },
      axisLine: { lineStyle: { color: ct.grid } },
    },
    yAxis: {
      type: 'value' as const,
      max: normalized ? 100 : assetNames.length * 100,
      axisLabel: {
        color: ct.axisLabel,
        formatter: normalized ? (v: number) => `${v}%` : undefined,
      },
      splitLine: { lineStyle: { color: ct.grid } },
    },
    series,
    grid: { top: 20, bottom: 80, left: 50, right: 20 },
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-2 justify-end">
        <span className="text-xs text-muted-foreground">Scale:</span>
        <button
          onClick={() => setNormalized(false)}
          className={`px-2 py-0.5 text-xs rounded border transition-colors ${
            !normalized ? 'border-primary text-primary' : 'border-border text-muted-foreground'
          }`}
        >
          Absolute
        </button>
        <button
          onClick={() => setNormalized(true)}
          className={`px-2 py-0.5 text-xs rounded border transition-colors ${
            normalized ? 'border-primary text-primary' : 'border-border text-muted-foreground'
          }`}
        >
          0–100%
        </button>
      </div>
      <ReactECharts option={option} style={{ height: 320 }} opts={{ renderer: 'svg' }} notMerge />
    </div>
  )
}
