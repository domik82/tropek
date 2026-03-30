// src/features/evaluations/components/SLIBreakdownTable.tsx
import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { fmt } from '@/lib/format'
import { STATUS_TEXT } from '@/lib/status'
import type { IndicatorResult, SliMetadata } from '../types'

function fmtPct(v: number | null | undefined): string {
  if (v == null) return '—'
  const sign = v >= 0 ? '+' : ''
  return `${sign}${v.toFixed(2)}%`
}

const LOW_CONFIDENCE_THRESHOLD = 20

interface SliGroup {
  prefix: string
  indicators: IndicatorResult[]
  metadata?: SliMetadata
}

function groupIndicators(
  indicators: IndicatorResult[],
  sliMetadata?: Record<string, SliMetadata>,
): (IndicatorResult | SliGroup)[] {
  if (!sliMetadata || Object.keys(sliMetadata).length === 0) {
    return indicators
  }

  const result: (IndicatorResult | SliGroup)[] = []
  const grouped = new Set<string>()

  // Build groups from metadata keys
  const prefixMap = new Map<string, IndicatorResult[]>()
  for (const ind of indicators) {
    const dotIdx = ind.metric.lastIndexOf('.')
    if (dotIdx > 0) {
      const prefix = ind.metric.substring(0, dotIdx)
      if (sliMetadata[prefix]) {
        if (!prefixMap.has(prefix)) prefixMap.set(prefix, [])
        prefixMap.get(prefix)!.push(ind)
        grouped.add(ind.metric)
      }
    }
  }

  // Emit items in original order, replacing first member of each group with the group
  const emittedGroups = new Set<string>()
  for (const ind of indicators) {
    if (grouped.has(ind.metric)) {
      const dotIdx = ind.metric.lastIndexOf('.')
      const prefix = ind.metric.substring(0, dotIdx)
      if (!emittedGroups.has(prefix)) {
        emittedGroups.add(prefix)
        result.push({
          prefix,
          indicators: prefixMap.get(prefix)!,
          metadata: sliMetadata[prefix],
        })
      }
    } else {
      result.push(ind)
    }
  }

  return result
}

function isGroup(item: IndicatorResult | SliGroup): item is SliGroup {
  return 'prefix' in item && 'indicators' in item
}

interface Props {
  indicators: IndicatorResult[]
  sliMetadata?: Record<string, SliMetadata>
  onIndicatorClick?: (metric: string, tabGroup: string) => void
}

export function SLIBreakdownTable({ indicators, sliMetadata, onIndicatorClick }: Props) {
  const [selectedMetric, setSelectedMetric] = useState<string | null>(null)
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set())

  const items = groupIndicators(indicators, sliMetadata)

  function handleRowClick(metric: string, tabGroup: string) {
    setSelectedMetric(metric)
    onIndicatorClick?.(metric, tabGroup)
  }

  function toggleGroup(prefix: string) {
    setCollapsedGroups(prev => {
      const next = new Set(prev)
      if (next.has(prefix)) next.delete(prefix)
      else next.add(prefix)
      return next
    })
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-table-row-bg">
      <table className="w-full text-sm text-left">
        <thead className="text-xs uppercase text-muted-foreground bg-table-header-bg border-b border-border">
          <tr>
            <th className="px-2 py-3 text-center w-6 text-indicator-key-sli" title="Key SLI">◆</th>
            <th className="px-4 py-3">Indicator</th>
            <th className="px-4 py-3 text-right">Value</th>
            <th className="px-4 py-3 text-right">Baseline</th>
            <th className="px-4 py-3 text-right">Δ</th>
            <th className="px-4 py-3 text-right">Weight</th>
            <th className="px-4 py-3 text-right">Score</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Pass criteria</th>
            <th className="px-4 py-3">Warn criteria</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, idx) => {
            if (isGroup(item)) {
              const collapsed = collapsedGroups.has(item.prefix)
              const meta = item.metadata
              const lowConfidence = meta && meta.missing_pct > LOW_CONFIDENCE_THRESHOLD
              return (
                <GroupRows
                  key={item.prefix}
                  group={item}
                  collapsed={collapsed}
                  lowConfidence={!!lowConfidence}
                  onToggle={() => toggleGroup(item.prefix)}
                  selectedMetric={selectedMetric}
                  onRowClick={handleRowClick}
                  onIndicatorClick={onIndicatorClick}
                  startIdx={idx}
                />
              )
            }
            return (
              <IndicatorRow
                key={item.metric}
                ind={item}
                idx={idx}
                isSelected={item.metric === selectedMetric}
                onClick={handleRowClick}
                onIndicatorClick={onIndicatorClick}
              />
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

interface GroupRowsProps {
  group: SliGroup
  collapsed: boolean
  lowConfidence: boolean
  onToggle: () => void
  selectedMetric: string | null
  onRowClick: (metric: string, tabGroup: string) => void
  onIndicatorClick?: (metric: string, tabGroup: string) => void
  startIdx: number
}

function GroupRows({ group, collapsed, lowConfidence, onToggle, selectedMetric, onRowClick, onIndicatorClick, startIdx }: GroupRowsProps) {
  const meta = group.metadata
  return (
    <>
      {/* Group header row */}
      <tr
        className="bg-muted/30 border-b border-border cursor-pointer hover:bg-muted/50 transition-colors"
        onClick={onToggle}
      >
        <td className="px-2 py-2" />
        <td className="px-4 py-2 font-medium" colSpan={9}>
          <div className="flex items-center gap-2">
            {collapsed
              ? <ChevronRight className="size-3.5 text-muted-foreground" />
              : <ChevronDown className="size-3.5 text-muted-foreground" />
            }
            <span className="text-foreground">{group.prefix}</span>
            {meta && (
              <span className="text-xs text-muted-foreground font-mono">
                {meta.actual_samples}/{meta.expected_samples} samples ({meta.missing_pct.toFixed(1)}% missing)
              </span>
            )}
            {lowConfidence && (
              <span className="text-xs text-warning px-1.5 py-0.5 rounded bg-warning/10 border border-warning/20">
                low confidence
              </span>
            )}
          </div>
        </td>
      </tr>
      {/* Child rows */}
      {!collapsed && group.indicators.map((ind, i) => {
        const methodSuffix = ind.metric.substring(group.prefix.length + 1)
        return (
          <IndicatorRow
            key={ind.metric}
            ind={ind}
            idx={startIdx + 1 + i}
            isSelected={ind.metric === selectedMetric}
            onClick={onRowClick}
            onIndicatorClick={onIndicatorClick}
            displayName={methodSuffix}
            indented
          />
        )
      })}
    </>
  )
}

interface IndicatorRowProps {
  ind: IndicatorResult
  idx: number
  isSelected: boolean
  onClick: (metric: string, tabGroup: string) => void
  onIndicatorClick?: (metric: string, tabGroup: string) => void
  displayName?: string
  indented?: boolean
}

function IndicatorRow({ ind, idx, isSelected, onClick, onIndicatorClick, displayName, indented }: IndicatorRowProps) {
  const zebraBase = idx % 2 === 0 ? 'bg-table-row-bg' : 'bg-table-row-alt'
  const rowBg = isSelected ? 'bg-table-row-selected' : zebraBase
  const rowHover = isSelected ? 'hover:bg-table-row-selected' : 'hover:bg-table-row-hover'
  const rowRing = isSelected ? 'ring-1 ring-inset ring-muted-foreground/60' : ''
  const label = displayName ?? (ind.display_name || ind.metric)

  return (
    <tr
      onClick={() => onClick(ind.metric, ind.tab_group ?? 'summary')}
      className={`transition-colors group border-b border-border/60 last:border-0 cursor-pointer ${rowBg} ${rowHover} ${rowRing}`}
    >
      <td className="px-2 py-3 text-center">
        {ind.key_sli && (
          <span className="text-indicator-key-sli text-xs leading-none" title="Key SLI">◆</span>
        )}
      </td>
      <td className={`px-4 py-3 font-medium whitespace-nowrap ${indented ? 'pl-10' : ''}`}>
        {onIndicatorClick ? (
          <button
            className="text-left group/name"
            title={`${ind.metric} — click to go to trend chart`}
          >
            <span className="flex items-center gap-1">
              <span className="text-foreground group-hover/name:text-link-hover transition-colors underline decoration-dotted underline-offset-2 decoration-muted-foreground/60 group-hover/name:decoration-link-hover">
                {label}
              </span>
              <span className="text-muted-foreground/60 group-hover/name:text-link-hover text-xs">↓</span>
            </span>
          </button>
        ) : (
          <span className="text-foreground" title={ind.metric}>
            {label}
          </span>
        )}
      </td>
      <td className="px-4 py-3 text-right font-mono">{fmt(ind.value)}</td>
      <td className="px-4 py-3 text-right font-mono text-muted-foreground">{fmt(ind.compared_value)}</td>
      <td className="px-4 py-3 text-right font-mono">
        {ind.change_relative_pct != null ? (
          <span className={STATUS_TEXT[ind.status] ?? 'text-foreground'}>
            {fmtPct(ind.change_relative_pct)}
          </span>
        ) : '—'}
      </td>
      <td className="px-4 py-3 text-right text-muted-foreground">{ind.weight}</td>
      <td className="px-4 py-3 text-right font-mono">{fmt(ind.score)}</td>
      <td className={`px-4 py-3 font-semibold uppercase text-xs ${STATUS_TEXT[ind.status] ?? ''}`}>
        {ind.status}
      </td>
      <td className="px-4 py-3 text-xs text-muted-foreground">
        {ind.pass_targets?.map((t, i) => (
          <div key={i} className={`font-mono ${t.violated ? 'text-destructive-form-text' : ''}`}>
            {t.criteria}{t.violated && ' ✗'}
          </div>
        ))}
      </td>
      <td className="px-4 py-3 text-xs text-muted-foreground">
        {ind.warning_targets?.map((t, i) => (
          <div key={i} className="font-mono">{t.criteria}</div>
        ))}
      </td>
    </tr>
  )
}
