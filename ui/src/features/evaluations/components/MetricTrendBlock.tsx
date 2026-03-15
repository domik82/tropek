// src/features/evaluations/components/MetricTrendBlock.tsx
import ReactECharts from 'echarts-for-react'
import { useState } from 'react'
import { useTrend } from '../hooks'
import { RESULT_COLOUR } from '../constants'
import { computeRelativeThresholdSeries } from '@/utils/metrics'
import type { IndicatorResult } from '../types'

interface Props {
  evalId: string
  indicator: IndicatorResult
}

function isRelativeCriteria(c?: string | null): boolean {
  return !!c && c.startsWith('<=+')
}

function scrollToTable() {
  document.getElementById('sli-table')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const STATUS_TEXT: Record<string, string> = {
  pass:    'text-[#7dc540]',
  warning: 'text-[#e6be00]',
  fail:    'text-[#dc172a]',
}

export function MetricTrendBlock({ evalId, indicator }: Props) {
  const { data: trend, isLoading } = useTrend(evalId, indicator.metric)
  const [yMin, setYMin] = useState('')
  const [yMax, setYMax] = useState('')
  const [showPass, setShowPass] = useState(true)
  const [showWarn, setShowWarn] = useState(true)

  const passTarget = indicator.pass_targets?.[0] ?? null
  const warnTarget = indicator.warning_targets?.[0] ?? null
  const passCriteria = passTarget?.criteria ?? null
  const warnCriteria = warnTarget?.criteria ?? null

  const times = (trend ?? []).map(p => p.timestamp.slice(0, 16).replace('T', ' '))

  const chartData = (trend ?? []).map(p => ({
    value: p.value,
    itemStyle: {
      color: RESULT_COLOUR[p.result] ?? '#6b7280',
      borderColor: p.eval_id === evalId ? '#ffffff' : 'transparent',
      borderWidth: 2,
    },
  }))

  const passRel = showPass && isRelativeCriteria(passCriteria)
    ? computeRelativeThresholdSeries(trend ?? [], passCriteria!)
    : []
  const warnRel = showWarn && isRelativeCriteria(warnCriteria)
    ? computeRelativeThresholdSeries(trend ?? [], warnCriteria!)
    : []

  const markLines: object[] = []
  if (showPass && passTarget?.target_value != null && !passRel.length)
    markLines.push({
      yAxis: passTarget.target_value,
      lineStyle: { color: RESULT_COLOUR.pass, type: 'dashed', width: 1.5 },
      label: { formatter: `pass: ${passCriteria ?? passTarget.target_value}`, color: RESULT_COLOUR.pass, fontSize: 10 },
    })
  if (showWarn && warnTarget?.target_value != null && !warnRel.length)
    markLines.push({
      yAxis: warnTarget.target_value,
      lineStyle: { color: RESULT_COLOUR.warning, type: 'dashed', width: 1.5 },
      label: { formatter: `warn: ${warnCriteria ?? warnTarget.target_value}`, color: RESULT_COLOUR.warning, fontSize: 10 },
    })

  const option = {
    animation: false,
    backgroundColor: 'transparent',
    grid: { top: 16, bottom: 52, left: 56, right: 16 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1a2030',
      borderColor: '#374151',
      textStyle: { color: '#e2e8f0', fontSize: 12 },
    },
    xAxis: {
      type: 'category',
      data: times,
      axisLabel: { color: '#6b7280', fontSize: 9, rotate: 35 },
      axisLine: { lineStyle: { color: '#2d3748' } },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      min: yMin !== '' ? parseFloat(yMin) : undefined,
      max: yMax !== '' ? parseFloat(yMax) : undefined,
      axisLabel: { color: '#6b7280', fontSize: 10 },
      splitLine: { lineStyle: { color: '#1a2030' } },
    },
    series: [
      {
        type: 'line',
        data: chartData,
        symbol: 'circle',
        symbolSize: (_val: unknown, params: { dataIndex: number }) =>
          (trend ?? [])[params.dataIndex]?.eval_id === evalId ? 10 : 6,
        lineStyle: { color: '#374151', width: 1.5 },
        ...(markLines.length ? {
          markLine: {
            silent: true,
            symbol: 'none',
            data: markLines.map((ml: object) => {
              const m = ml as { yAxis: number; lineStyle: object; label: object }
              return { yAxis: m.yAxis, lineStyle: m.lineStyle, label: { ...m.label, position: 'insideStartTop' } }
            }),
          },
        } : {}),
      },
      ...(passRel.length ? [{
        type: 'line', data: passRel, symbol: 'none', silent: true,
        lineStyle: { color: RESULT_COLOUR.pass, type: 'dashed' as const, width: 1.5 },
        tooltip: { show: false },
      }] : []),
      ...(warnRel.length ? [{
        type: 'line', data: warnRel, symbol: 'none', silent: true,
        lineStyle: { color: RESULT_COLOUR.warning, type: 'dashed' as const, width: 1.5 },
        tooltip: { show: false },
      }] : []),
    ],
  }

  return (
    <div id={`trend-${indicator.metric}`} className="bg-[#111827] border border-slate-700 rounded-xl p-4 scroll-mt-4">
      <div className="flex items-center justify-between mb-1">
        <span className={`text-xs font-semibold uppercase ${STATUS_TEXT[indicator.status] ?? 'text-slate-400'}`}>
          {indicator.status}
        </span>
        <button
          onClick={scrollToTable}
          className="text-sm font-medium text-slate-200 hover:text-indigo-300 transition-colors"
          title="Back to SLI table"
        >
          ↑ top
        </button>
      </div>

      {isLoading ? (
        <div>
          <div className="text-xs text-slate-500 mb-2">{indicator.display_name}</div>
          <div className="h-[200px] flex items-center justify-center text-slate-600 text-xs">loading…</div>
        </div>
      ) : (
        <div>
          <div className="flex items-center gap-3 mb-1">
            <span className="text-xs font-semibold text-slate-300" title={indicator.metric}>
              {indicator.display_name || indicator.metric}
            </span>
            <div className="flex items-center gap-1 ml-auto text-xs">
              {(passTarget?.target_value != null || isRelativeCriteria(passCriteria)) && (
                <button
                  onClick={() => setShowPass(v => !v)}
                  className={`px-2 py-0.5 rounded border text-[10px] font-medium transition-colors ${
                    showPass
                      ? 'border-[#7dc540]/50 text-[#7dc540] bg-[#7dc540]/10'
                      : 'border-slate-700 text-slate-600 bg-transparent'
                  }`}
                >
                  pass {passCriteria ?? passTarget?.target_value}
                </button>
              )}
              {(warnTarget?.target_value != null || isRelativeCriteria(warnCriteria)) && (
                <button
                  onClick={() => setShowWarn(v => !v)}
                  className={`px-2 py-0.5 rounded border text-[10px] font-medium transition-colors ${
                    showWarn
                      ? 'border-[#e6be00]/50 text-[#e6be00] bg-[#e6be00]/10'
                      : 'border-slate-700 text-slate-600 bg-transparent'
                  }`}
                >
                  warn {warnCriteria ?? warnTarget?.target_value}
                </button>
              )}
            </div>
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <label className="flex items-center gap-1">
                Y <input
                  type="number" value={yMin} onChange={e => setYMin(e.target.value)}
                  placeholder="min" className="w-14 px-1 py-0.5 bg-slate-800 border border-slate-700 rounded text-slate-300"
                />
              </label>
              <label className="flex items-center gap-1">
                – <input
                  type="number" value={yMax} onChange={e => setYMax(e.target.value)}
                  placeholder="max" className="w-14 px-1 py-0.5 bg-slate-800 border border-slate-700 rounded text-slate-300"
                />
              </label>
            </div>
          </div>
          <ReactECharts option={option} style={{ height: 200 }} opts={{ renderer: 'svg' }} notMerge />
        </div>
      )}
    </div>
  )
}
