import { describe, it, expect, vi } from 'vitest'
import type { QueryClient } from '@tanstack/react-query'
import { invalidateColumnQueries } from './invalidate-column-queries'
import { evaluationKeys } from '@/lib/queryKeys'

describe('invalidateColumnQueries', () => {
  it('invalidates detail, list, heatmap, and trend keys', () => {
    const invalidateQueries = vi.fn()
    const queryClient = { invalidateQueries } as unknown as QueryClient

    invalidateColumnQueries(queryClient, ['sloeval-a', 'sloeval-b'])

    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: evaluationKeys.detail('sloeval-a') })
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: evaluationKeys.detail('sloeval-b') })
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: evaluationKeys.all })
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: evaluationKeys.allHeatmaps })
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: evaluationKeys.allTrends })
  })

  it('handles empty id list by only invalidating list-level keys', () => {
    const invalidateQueries = vi.fn()
    const queryClient = { invalidateQueries } as unknown as QueryClient

    invalidateColumnQueries(queryClient, [])

    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: evaluationKeys.all })
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: evaluationKeys.allHeatmaps })
    expect(invalidateQueries).not.toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: evaluationKeys.detail(expect.any(String)) }),
    )
  })
})
