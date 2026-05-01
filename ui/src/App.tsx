// src/App.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Routes, Route, NavLink, Navigate } from 'react-router-dom'
import { EvaluationDetailPage } from './pages/EvaluationDetailPage'
import { SloRegistryPage } from './pages/SloRegistryPage'
import { AssetsPage } from './pages/AssetsPage'
import { AssetNavigatorPage } from './pages/AssetNavigatorPage'
import { MetricExplorerPage } from './pages/MetricExplorerPage'
import { CategoryManagementPage } from './features/note-categories/components/CategoryManagementPage'
import { ChangePointsPage } from './features/change-points/components/ChangePointsPage'
import { Button } from './components/ui/button'
import { ThemeProvider, useTheme } from './lib/theme-context'
import { TimeRangeProvider } from './lib/time-range-context'
import { ErrorBoundary } from './components/ErrorBoundary'

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000 } },
})

const NAV_ITEMS = [
  { to: '/navigator', label: 'Navigator' },
  { to: '/change-points', label: 'Change Points' },
  { to: '/slos', label: 'SLOs' },
  { to: '/assets', label: 'Assets' },
]

function NavControls() {
  const { theme, setTheme, fontSize, setFontSize } = useTheme()

  return (
    <div className="flex items-center gap-2 ml-auto">
      {/* Font size control */}
      <div className="flex items-center border border-border rounded overflow-hidden text-xs">
        <Button
          variant="ghost"
          size="icon-xs"
          onClick={() => setFontSize(fontSize - 1)}
          className="rounded-none text-muted-foreground"
          aria-label="Decrease font size"
        >
          −
        </Button>
        <span className="px-2 py-1 text-muted-foreground tabular-nums">{fontSize}px</span>
        <Button
          variant="ghost"
          size="icon-xs"
          onClick={() => setFontSize(fontSize + 1)}
          className="rounded-none text-muted-foreground"
          aria-label="Increase font size"
        >
          +
        </Button>
      </div>

      {/* Theme toggle */}
      <div className="flex border border-border rounded overflow-hidden text-xs">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setTheme('dark')}
          className={`rounded-none ${theme === 'dark' ? 'bg-muted text-foreground font-semibold' : 'text-muted-foreground'}`}
        >
          🌙 Dark
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setTheme('current')}
          className={`rounded-none ${theme === 'current' ? 'bg-muted text-foreground font-semibold' : 'text-muted-foreground'}`}
          title="Original shadcn neutral dark (comparison)"
        >
          ◑ Alt
        </Button>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <ThemeProvider>
      <TimeRangeProvider>
        <QueryClientProvider client={queryClient}>
          <BrowserRouter>
          <div className="min-h-screen bg-background text-foreground">
            <nav className="border-b border-border px-6 py-3 flex items-center gap-6">
              <span className="font-bold text-sm tracking-widest" style={{ color: 'var(--tropek-logo)' }}>TROPEK</span>
              {NAV_ITEMS.map(item => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    `text-sm transition-colors ${isActive ? 'text-foreground' : 'text-muted-foreground hover:text-foreground'}`
                  }
                >
                  {item.label}
                </NavLink>
              ))}
              <NavControls />
            </nav>
            <main>
              <ErrorBoundary>
                <Routes>
                  <Route path="/" element={<Navigate to="/navigator" replace />} />
                  <Route path="/navigator" element={<AssetNavigatorPage />} />
                  <Route path="/explorer" element={<MetricExplorerPage />} />
                  <Route path="/evaluations/:id" element={<EvaluationDetailPage />} />
                  <Route path="/slos" element={<SloRegistryPage />} />
                  <Route path="/assets" element={<AssetsPage />} />
                  <Route path="/change-points" element={<ChangePointsPage />} />
                  <Route path="/settings/note-categories" element={<CategoryManagementPage />} />
                </Routes>
              </ErrorBoundary>
            </main>
          </div>
        </BrowserRouter>
        </QueryClientProvider>
      </TimeRangeProvider>
    </ThemeProvider>
  )
}
