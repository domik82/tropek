// src/features/evaluations/hooks.ts
// Custom hooks = service layer. Components never call fetch directly — they call these hooks.

import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query'
import { useState, useEffect, useRef, useMemo } from 'react'
import { evaluationKeys } from '@/lib/queryKeys'
import {
  fetchEvaluations,
  fetchEvaluationDetail,
  fetchTrend,
  addAnnotation,
  hideAnnotation,
  invalidateEvaluation,
  restoreEvaluation,
  overrideStatus,
  pinBaseline,
  reEvaluate,
} from './api'
import { useTimeRange } from '@/lib/time-range-context'
import type { EvaluationFilters, EvaluationSummary, ColumnDef, ReEvaluatePayload } from './types'
import { FIXED_COLS, DEFAULT_VISIBLE_KEYS } from './constants'

// ── List ──────────────────────────────────────────────────────────────────────

export function useEvaluations(filters: EvaluationFilters = {}) {
  const { from, to } = useTimeRange()
  const merged = { ...filters, from, ...(to ? { to } : {}) }
  const query = useQuery({
    queryKey: evaluationKeys.list(merged),
    queryFn: () => fetchEvaluations(merged),
    placeholderData: keepPreviousData,
  })
  return {
    ...query,
    data: query.data?.items,
    truncated: query.data?.truncated ?? false,
    total: query.data?.total ?? 0,
  }
}

// ── Detail ────────────────────────────────────────────────────────────────────

export function useEvaluationDetail(id: string | undefined) {
  return useQuery({
    queryKey: evaluationKeys.detail(id ?? ''),
    queryFn: () => fetchEvaluationDetail(id!),
    enabled: !!id,
    placeholderData: keepPreviousData,
  })
}

// ── Trend ─────────────────────────────────────────────────────────────────────

export function useTrend(evalId: string, metric: string) {
  return useQuery({
    queryKey: evaluationKeys.trend(evalId, metric),
    queryFn: () => fetchTrend(evalId, metric),
    enabled: !!evalId && !!metric,
    staleTime: Infinity,
  })
}

// ── Mutations ─────────────────────────────────────────────────────────────────

export function useAddAnnotation(evalId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: { content: string; category?: string; author?: string }) =>
      addAnnotation(evalId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: evaluationKeys.detail(evalId) })
    },
  })
}

export function useHideAnnotation(evalId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: { annotationId: string; reason: string; author?: string }) =>
      hideAnnotation(evalId, payload.annotationId, {
        reason: payload.reason,
        author: payload.author,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: evaluationKeys.detail(evalId) })
      qc.invalidateQueries({ queryKey: evaluationKeys.all })
    },
  })
}

export function useInvalidateEvaluation(evalId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: { note: string; author: string }) =>
      invalidateEvaluation(evalId, payload.note),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: evaluationKeys.detail(evalId) })
      qc.invalidateQueries({ queryKey: evaluationKeys.all })
      qc.invalidateQueries({ queryKey: ['evaluation-names'] })
      qc.invalidateQueries({ queryKey: ['metric-heatmap'] })
    },
  })
}

export function useRestoreEvaluation(evalId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => restoreEvaluation(evalId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: evaluationKeys.detail(evalId) })
      qc.invalidateQueries({ queryKey: evaluationKeys.all })
      qc.invalidateQueries({ queryKey: ['evaluation-names'] })
      qc.invalidateQueries({ queryKey: ['metric-heatmap'] })
    },
  })
}

export function useOverrideStatus(evalId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: { new_result: string; reason: string; author: string }) =>
      overrideStatus(evalId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: evaluationKeys.detail(evalId) })
      qc.invalidateQueries({ queryKey: evaluationKeys.all })
      qc.invalidateQueries({ queryKey: ['metric-heatmap'] })
    },
  })
}

export function usePinBaseline(evalId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: { reason: string; author: string }) =>
      pinBaseline(evalId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: evaluationKeys.detail(evalId) })
      qc.invalidateQueries({ queryKey: evaluationKeys.all })
    },
  })
}

export function useReEvaluate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: ReEvaluatePayload) => reEvaluate(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: evaluationKeys.all })
      qc.invalidateQueries({ queryKey: ['evaluation-names'] })
      qc.invalidateQueries({ queryKey: ['metric-heatmap'] })
    },
  })
}

// ── Column visibility ─────────────────────────────────────────────────────────

const FIXED_KEYS = new Set(FIXED_COLS.map(c => c.key))

function prettyLabel(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase())
}

/**
 * Discover dynamic columns from evaluation data.
 * Scans asset_snapshot.tags and evaluation_metadata across all evals,
 * deduplicates, and returns ColumnDef[] for keys not already in FIXED_COLS.
 */
export function useDynamicColumns(evals: EvaluationSummary[]): ColumnDef[] {
  return useMemo(() => {
    const seen = new Set<string>()
    const cols: ColumnDef[] = []
    for (const ev of evals) {
      for (const key of Object.keys(ev.asset_snapshot.tags ?? {})) {
        if (!FIXED_KEYS.has(key) && !seen.has(key)) {
          seen.add(key)
          cols.push({ key, label: prettyLabel(key), required: false })
        }
      }
      for (const key of Object.keys(ev.evaluation_metadata ?? {})) {
        if (!FIXED_KEYS.has(key) && !seen.has(key)) {
          seen.add(key)
          cols.push({ key, label: prettyLabel(key), required: false })
        }
      }
    }
    return cols
  }, [evals])
}

/**
 * Pure helper — exported so it can be unit-tested without React.
 * Guards required columns and toggles membership in the visible set.
 */
export function toggleColumnKey(
  prev: Set<string>,
  key: string,
  allCols: ColumnDef[]
): Set<string> {
  const col = allCols.find(c => c.key === key)
  if (!col || col.required) return prev
  const next = new Set(prev)
  next.has(key) ? next.delete(key) : next.add(key)
  return next
}

export function useColumnVisibility(dynamicCols: ColumnDef[]) {
  const allCols = [...FIXED_COLS, ...dynamicCols]
  const [visibleKeys, setVisibleKeys] = useState<Set<string>>(
    () => new Set([...DEFAULT_VISIBLE_KEYS, ...dynamicCols.map(c => c.key)])
  )
  const [open, setOpen] = useState(false)
  const pickerRef = useRef<HTMLTableCellElement>(null)

  // Auto-add newly discovered dynamic columns to visible set
  useEffect(() => {
    setVisibleKeys(prev => {
      const newKeys = dynamicCols.filter(c => !prev.has(c.key))
      if (newKeys.length === 0) return prev
      const next = new Set(prev)
      for (const c of newKeys) next.add(c.key)
      return next
    })
  }, [dynamicCols])

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (pickerRef.current && !pickerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    if (open) document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  function toggle(key: string) {
    setVisibleKeys(prev => toggleColumnKey(prev, key, allCols))
  }

  return { allCols, visibleKeys, open, setOpen, toggle, pickerRef }
}
