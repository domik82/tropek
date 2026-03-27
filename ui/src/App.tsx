// src/App.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Routes, Route, NavLink, Navigate } from 'react-router-dom'
import { EvaluationDetailPage } from './pages/EvaluationDetailPage'
import { SloRegistryPage } from './pages/SloRegistryPage'
import { AssetsPage } from './pages/AssetsPage'
import { AssetNavigatorPage } from './pages/AssetNavigatorPage'
import { MetricExplorerPage } from './pages/MetricExplorerPage'
import { ThemeProvider, useTheme } from './lib/theme-context'
import { TimeRangeProvider } from './lib/time-range-context'

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000 } },
})

const NAV_ITEMS = [
  { to: '/navigator', label: 'Navigator' },
  { to: '/slos', label: 'SLOs' },
  { to: '/assets', label: 'Assets' },
]

function NavControls() {
  const { theme, setTheme, fontSize, setFontSize } = useTheme()

  return (
    <div className="flex items-center gap-2 ml-auto">
      {/* Font size control */}
      <div className="flex items-center border border-border rounded overflow-hidden text-xs">
        <button
          onClick={() => setFontSize(fontSize - 1)}
          className="px-2 py-1 hover:bg-muted transition-colors text-muted-foreground"
          aria-label="Decrease font size"
        >
          −
        </button>
        <span className="px-2 py-1 text-muted-foreground tabular-nums">{fontSize}px</span>
        <button
          onClick={() => setFontSize(fontSize + 1)}
          className="px-2 py-1 hover:bg-muted transition-colors text-muted-foreground"
          aria-label="Increase font size"
        >
          +
        </button>
      </div>

      {/* Theme toggle */}
      <div className="flex border border-border rounded overflow-hidden text-xs">
        <button
          onClick={() => setTheme('forest')}
          className={`px-3 py-1 transition-colors ${theme === 'forest' ? 'bg-muted text-foreground font-semibold' : 'text-muted-foreground hover:bg-muted/50'}`}
        >
          🌙 Dark
        </button>
        <button
          onClick={() => setTheme('current')}
          className={`px-3 py-1 transition-colors ${theme === 'current' ? 'bg-muted text-foreground font-semibold' : 'text-muted-foreground hover:bg-muted/50'}`}
          title="Original shadcn neutral dark (comparison)"
        >
          ◑ Alt
        </button>
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
              <span className="font-bold text-sm tracking-widest" style={{ color: 'oklch(68.628% 0.185 148.958)' }}>TROPEK</span>
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
              <Routes>
                <Route path="/" element={<Navigate to="/navigator" replace />} />
                <Route path="/navigator" element={<AssetNavigatorPage />} />
                <Route path="/explorer" element={<MetricExplorerPage />} />
                <Route path="/evaluations/:id" element={<EvaluationDetailPage />} />
                <Route path="/slos" element={<SloRegistryPage />} />
                <Route path="/assets" element={<AssetsPage />} />
              </Routes>
            </main>
          </div>
        </BrowserRouter>
        </QueryClientProvider>
      </TimeRangeProvider>
    </ThemeProvider>
  )
}
