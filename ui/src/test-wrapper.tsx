import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { ChartPreferencesProvider } from '@/lib/chart-preferences-context'

// eslint-disable-next-line react-refresh/only-export-components
export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
}

export function TestWrapper({ children }: { children: ReactNode }) {
  const client = createTestQueryClient()
  // ChartPreferencesProvider is an app-root provider (mounted in App.tsx alongside the query
  // client), so mirror it here — any component under test that transitively renders a chart
  // control can call useChartPreferences() without each test re-wrapping it.
  return (
    <QueryClientProvider client={client}>
      <ChartPreferencesProvider>{children}</ChartPreferencesProvider>
    </QueryClientProvider>
  )
}
