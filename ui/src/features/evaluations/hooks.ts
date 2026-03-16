// src/features/evaluations/hooks.ts
// Custom hooks = service layer. Components never call fetch directly — they call these hooks.

import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query'
import { useState, useEffect, useRef } from 'react'
import { evaluationKeys } from '@/lib/queryKeys'
import {
  fetchEvaluations,
  fetchEvaluationDetail,
  fetchTrend,
  addAnnotation,
  invalidateEvaluation,
  overrideStatus,
  pinBaseline,
} from './api'
import type { EvaluationFilters, ColumnDef } from './types'
import { FIXED_COLS, DEFAULT_VISIBLE_KEYS } from './constants'

// ── List ──────────────────────────────────────────────────────────────────────

export function useEvaluations(filters: EvaluationFilters = {}) {
  return useQuery({
    queryKey: evaluationKeys.list(filters),
    queryFn: () => fetchEvaluations(filters),
    placeholderData: keepPreviousData,
  })
}

// ── Detail ────────────────────────────────────────────────────────────────────

export function useEvaluationDetail(id: string | undefined) {
  return useQuery({
    queryKey: evaluationKeys.detail(id ?? ''),
    queryFn: () => fetchEvaluationDetail(id!),
    enabled: !!id,
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

export function useInvalidateEvaluation(evalId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (note: string) => invalidateEvaluation(evalId, note),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: evaluationKeys.detail(evalId) })
      qc.invalidateQueries({ queryKey: evaluationKeys.all })
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

// ── Column visibility ─────────────────────────────────────────────────────────

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
    new Set(DEFAULT_VISIBLE_KEYS)
  )
  const [open, setOpen] = useState(false)
  const pickerRef = useRef<HTMLTableCellElement>(null)

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
