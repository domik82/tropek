import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor, cleanup } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { useSloGroups } from './hooks'
import * as api from './api'

vi.mock('./api')

let queryClient: QueryClient

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

describe('useSloGroups', () => {
  beforeEach(() => {
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    vi.resetAllMocks()
  })

  afterEach(() => {
    queryClient.cancelQueries()
    queryClient.clear()
    cleanup()
  })

  it('returns SLO groups from API', async () => {
    const groups = [
      {
        id: '1',
        name: 'g1',
        display_name: null,
        template_slo_name: 'tpl',
        template_slo_version: 1,
        gen_variables: { x: ['a'] },
        tags: {},
        author: null,
        version: 1,
        active: true,
        created_at: '',
        updated_at: '',
        generated_slo_count: 3,
      },
    ]
    vi.mocked(api.fetchSloGroups).mockResolvedValue(groups)

    const { result } = renderHook(() => useSloGroups(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(groups)
  })
})
