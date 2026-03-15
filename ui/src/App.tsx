// src/App.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Routes, Route, NavLink, Navigate } from 'react-router-dom'
import { EvaluationsPage } from './pages/EvaluationsPage'
import { EvaluationDetailPage } from './pages/EvaluationDetailPage'
import { SloRegistryPage } from './pages/SloRegistryPage'
import { AssetsPage } from './pages/AssetsPage'

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000 } },
})

const NAV_ITEMS = [
  { to: '/evaluations', label: 'Evaluations' },
  { to: '/slos', label: 'SLOs' },
  { to: '/assets', label: 'Assets' },
]

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="min-h-screen bg-gray-950 text-gray-100">
          <nav className="border-b border-gray-800 px-6 py-3 flex items-center gap-6">
            <span className="font-bold text-sm tracking-widest text-green-400">TROPEK</span>
            {NAV_ITEMS.map(item => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `text-sm transition-colors ${isActive ? 'text-white' : 'text-gray-400 hover:text-gray-200'}`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <main>
            <Routes>
              <Route path="/" element={<Navigate to="/evaluations" replace />} />
              <Route path="/evaluations" element={<EvaluationsPage />} />
              <Route path="/evaluations/:id" element={<EvaluationDetailPage />} />
              <Route path="/slos" element={<SloRegistryPage />} />
              <Route path="/assets" element={<AssetsPage />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
