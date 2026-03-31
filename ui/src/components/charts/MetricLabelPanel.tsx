// ui/src/components/charts/MetricLabelPanel.tsx
//
// Grouped, paginated label panel for MetricExplorerPage.
// Shows indicator names grouped by tab_group, with per-group All/None toggles
// and pagination across a flat ordered list of all labels.

import { useState } from 'react'
import { Button } from '@/components/ui/button'

// ── Types ─────────────────────────────────────────────────────────────────────

interface Indicator {
  metric: string
  display_name: string
  tab_group?: string
}

interface MetricLabelPanelProps {
  indicators: Indicator[]
  colors: Map<string, string>
  enabled: Set<string>
  onToggle: (metric: string) => void
  onGroupAll: (group: string) => void
  onGroupNone: (group: string) => void
}

// ── Constants ─────────────────────────────────────────────────────────────────

const LABELS_PER_PAGE = 50 // ~25 rows × 2 columns
const UNGROUPED_KEY = 'Other'

// ── Helpers ───────────────────────────────────────────────────────────────────

interface GroupedIndicators {
  groupName: string
  items: Indicator[]
}

function groupIndicators(indicators: Indicator[]): GroupedIndicators[] {
  const groupMap = new Map<string, Indicator[]>()

  for (const ind of indicators) {
    const key = ind.tab_group ?? UNGROUPED_KEY
    const existing = groupMap.get(key)
    if (existing) {
      existing.push(ind)
    } else {
      groupMap.set(key, [ind])
    }
  }

  // Move "Other" to the end if present alongside named groups
  const groups: GroupedIndicators[] = []
  let otherGroup: GroupedIndicators | null = null

  for (const [groupName, items] of groupMap.entries()) {
    if (groupName === UNGROUPED_KEY) {
      otherGroup = { groupName, items }
    } else {
      groups.push({ groupName, items })
    }
  }

  if (otherGroup) {
    groups.push(otherGroup)
  }

  return groups
}

// Flatten all grouped indicators into a single ordered list
function flattenGroups(groups: GroupedIndicators[]): Indicator[] {
  return groups.flatMap((g) => g.items)
}

// Given a flat paginated slice, re-group them preserving original group order
function regroupSlice(
  slice: Indicator[],
  allGroups: GroupedIndicators[],
): GroupedIndicators[] {
  const sliceSet = new Set(slice.map((i) => i.metric))
  const result: GroupedIndicators[] = []

  for (const group of allGroups) {
    const items = group.items.filter((i) => sliceSet.has(i.metric))
    if (items.length > 0) {
      result.push({ groupName: group.groupName, items })
    }
  }

  return result
}

// ── Component ─────────────────────────────────────────────────────────────────

export function MetricLabelPanel({
  indicators,
  colors,
  enabled,
  onToggle,
  onGroupAll,
  onGroupNone,
}: MetricLabelPanelProps) {
  const [page, setPage] = useState(0)

  const allGroups = groupIndicators(indicators)
  const flat = flattenGroups(allGroups)
  const totalPages = Math.max(1, Math.ceil(flat.length / LABELS_PER_PAGE))

  // Clamp page to valid range when indicators change
  const safePage = Math.min(page, totalPages - 1)

  const pageSlice = flat.slice(safePage * LABELS_PER_PAGE, (safePage + 1) * LABELS_PER_PAGE)
  const visibleGroups = regroupSlice(pageSlice, allGroups)

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto space-y-3 pr-1">
        {visibleGroups.map(({ groupName, items }) => (
          <div key={groupName}>
            {/* Group header */}
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide">
                {groupName}
              </span>
              <div className="flex gap-1">
                <Button
                  variant="ghost"
                  size="xs"
                  onClick={() => onGroupAll(groupName)}
                  className="h-auto px-1 py-0 text-[10px] text-muted-foreground hover:text-foreground"
                >
                  All
                </Button>
                <Button
                  variant="ghost"
                  size="xs"
                  onClick={() => onGroupNone(groupName)}
                  className="h-auto px-1 py-0 text-[10px] text-muted-foreground hover:text-foreground"
                >
                  None
                </Button>
              </div>
            </div>

            {/* Label grid */}
            <div className="grid grid-cols-2 gap-1">
              {items.map((ind) => {
                const isEnabled = enabled.has(ind.metric)
                const color = colors.get(ind.metric) ?? 'var(--state-disabled)'

                return (
                  <button
                    key={ind.metric}
                    onClick={() => onToggle(ind.metric)}
                    className={[
                      'flex items-center gap-1 px-1.5 py-0.5 rounded text-xs truncate text-left',
                      isEnabled
                        ? 'bg-secondary text-foreground'
                        : 'bg-transparent border border-transparent text-muted-foreground',
                    ].join(' ')}
                    style={
                      isEnabled
                        ? { border: `1px solid ${color}` }
                        : undefined
                    }
                    title={ind.display_name}
                  >
                    {/* Color dot */}
                    <span
                      className="flex-shrink-0 rounded-sm"
                      style={{
                        width: 8,
                        height: 8,
                        backgroundColor: isEnabled ? color : 'var(--state-disabled)',
                      }}
                    />
                    <span className="truncate">{ind.display_name}</span>
                  </button>
                )
              })}
            </div>
          </div>
        ))}
      </div>

      {/* Pagination footer */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 pt-2 border-t border-border text-xs text-muted-foreground">
          <Button
            variant="ghost"
            size="icon-xs"
            disabled={safePage === 0}
            onClick={() => setPage((p) => p - 1)}
          >
            ◀
          </Button>
          <span>
            {safePage + 1}/{totalPages}
          </span>
          <Button
            variant="ghost"
            size="icon-xs"
            disabled={safePage === totalPages - 1}
            onClick={() => setPage((p) => p + 1)}
          >
            ▶
          </Button>
        </div>
      )}
    </div>
  )
}
