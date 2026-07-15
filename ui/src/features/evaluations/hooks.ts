// src/features/evaluations/hooks.ts
// Custom hooks = service layer. Components never call fetch directly — they call these hooks.

import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query'
import { useState, useEffect, useRef, useMemo } from 'react'
import { evaluationKeys } from '@/lib/queryKeys'
import {
  fetchEvaluations,
  fetchEvaluationDetail,
  fetchTrend,
  fetchSloTrends,
  fetchColumnAnnotations,
  fetchTrendAnnotations,
  addAnnotation,
  addRunAnnotation,
  hideAnnotation,
  invalidateEvaluation,
  restoreEvaluation,
  overrideStatus,
  pinBaseline,
  reEvaluate,
} from './api'
import { useTimeRange } from '@/lib/time-range-context'
import type {
  AnnotationCreateInput,
  Evaluation,
  EvaluationFilters,
  OverrideStatusInput,
  ReEvaluateInput,
} from './domain'
import type { ColumnDef } from './ui-types'
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

// ── Column Annotations ───────────────────────────────────────────────────────

export function useTrendAnnotations(
  asset: string | undefined,
  slo: string | null | undefined,
) {
  return useQuery({
    queryKey: ['trend-annotations', asset, slo],
    queryFn: () => fetchTrendAnnotations(asset!, slo!),
    enabled: Boolean(asset && slo),
    staleTime: 60_000,
  })
}

export function useColumnAnnotations(evaluationId: string | undefined) {
  return useQuery({
    queryKey: evaluationKeys.columnAnnotations(evaluationId ?? ''),
    queryFn: () => fetchColumnAnnotations(evaluationId!),
    enabled: !!evaluationId,
    staleTime: Infinity,
  })
}

// ── Trend ─────────────────────────────────────────────────────────────────────

export function useTrend(assetName: string, sloName: string, metric: string) {
  const { from, to } = useTimeRange()
  const dateRange = { from, ...(to ? { to } : {}) }
  return useQuery({
    queryKey: evaluationKeys.trend(assetName, sloName, metric, dateRange),
    queryFn: () => fetchTrend(assetName, sloName, metric, dateRange),
    enabled: !!assetName && !!sloName && !!metric,
    staleTime: Infinity,
  })
}

export function useSloTrends(
  assetName: string,
  sloName: string,
  options?: { enabled?: boolean },
) {
  const { from, to } = useTimeRange()
  const dateRange = { from, ...(to ? { to } : {}) }
  return useQuery({
    queryKey: evaluationKeys.sloTrends(assetName, sloName, dateRange),
    queryFn: () => fetchSloTrends(assetName, sloName, dateRange),
    enabled: (options?.enabled ?? true) && !!assetName && !!sloName,
    staleTime: Infinity,
  })
}

// ── Mutations ─────────────────────────────────────────────────────────────────

export function useAddAnnotation(evalId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: AnnotationCreateInput) =>
      addAnnotation(evalId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: evaluationKeys.detail(evalId) })
      qc.invalidateQueries({ queryKey: [...evaluationKeys.all, 'column-annotations'] })
      // Trend charts overlay annotations via useTrendAnnotations — refetch so
      // the new note appears immediately alongside the existing ones.
      qc.invalidateQueries({ queryKey: ['trend-annotations'] })
      // Metric-heatmap carries has_notes per column — refetch so a newly added
      // note makes its indicator appear immediately.
      qc.invalidateQueries({ queryKey: evaluationKeys.allHeatmaps })
    },
  })
}

export function useAddRunAnnotation(runId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: AnnotationCreateInput) =>
      addRunAnnotation(runId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: evaluationKeys.detail(runId) })
      qc.invalidateQueries({ queryKey: [...evaluationKeys.all, 'column-annotations'] })
      qc.invalidateQueries({ queryKey: ['trend-annotations'] })
      qc.invalidateQueries({ queryKey: evaluationKeys.allHeatmaps })
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
      qc.invalidateQueries({ queryKey: [...evaluationKeys.all, 'column-annotations'] })
      qc.invalidateQueries({ queryKey: ['trend-annotations'] })
      // Hiding the last non-hidden annotation on a column flips has_notes back
      // to false — refetch the heatmap so the indicator disappears immediately.
      qc.invalidateQueries({ queryKey: evaluationKeys.allHeatmaps })
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
      qc.invalidateQueries({ queryKey: evaluationKeys.allNames })
      qc.invalidateQueries({ queryKey: evaluationKeys.allHeatmaps })
      qc.invalidateQueries({ queryKey: evaluationKeys.allTrends })
      qc.invalidateQueries({ queryKey: evaluationKeys.allSloTrends })
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
      qc.invalidateQueries({ queryKey: evaluationKeys.allNames })
      qc.invalidateQueries({ queryKey: evaluationKeys.allHeatmaps })
      qc.invalidateQueries({ queryKey: evaluationKeys.allTrends })
      qc.invalidateQueries({ queryKey: evaluationKeys.allSloTrends })
    },
  })
}

export function useOverrideStatus(evalId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: OverrideStatusInput) => overrideStatus(evalId, input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: evaluationKeys.detail(evalId) })
      qc.invalidateQueries({ queryKey: evaluationKeys.all })
      qc.invalidateQueries({ queryKey: evaluationKeys.allHeatmaps })
      qc.invalidateQueries({ queryKey: evaluationKeys.allTrends })
      qc.invalidateQueries({ queryKey: evaluationKeys.allSloTrends })
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
      qc.invalidateQueries({ queryKey: evaluationKeys.allTrends })
      qc.invalidateQueries({ queryKey: evaluationKeys.allSloTrends })
    },
  })
}

export function useReEvaluate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: ReEvaluateInput) => reEvaluate(input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: evaluationKeys.all })
      qc.invalidateQueries({ queryKey: evaluationKeys.allNames })
      qc.invalidateQueries({ queryKey: evaluationKeys.allHeatmaps })
      qc.invalidateQueries({ queryKey: evaluationKeys.allTrends })
      qc.invalidateQueries({ queryKey: evaluationKeys.allSloTrends })
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
 * Scans asset_snapshot.tags and variables across all evals,
 * deduplicates, and returns ColumnDef[] for keys not already in FIXED_COLS.
 */
export function useDynamicColumns(evals: Evaluation[]): ColumnDef[] {
  return useMemo(() => {
    const seen = new Set<string>()
    const cols: ColumnDef[] = []
    for (const ev of evals) {
      for (const key of Object.keys(ev.assetSnapshot.tags ?? {})) {
        if (!FIXED_KEYS.has(key) && !seen.has(key)) {
          seen.add(key)
          cols.push({ key, label: prettyLabel(key), required: false })
        }
      }
      for (const key of Object.keys(ev.variables ?? {})) {
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
  if (next.has(key)) next.delete(key); else next.add(key)
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
  /* eslint-disable react-hooks/set-state-in-effect -- sync derived state from prop change */
  useEffect(() => {
    setVisibleKeys(prev => {
      const newKeys = dynamicCols.filter(c => !prev.has(c.key))
      if (newKeys.length === 0) return prev
      const next = new Set(prev)
      for (const c of newKeys) next.add(c.key)
      return next
    })
  }, [dynamicCols])
  /* eslint-enable react-hooks/set-state-in-effect */

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
