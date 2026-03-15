# Quality Platform Phase 1 — Chunk 6: Prometheus Adapter + React UI

> **For agentic workers:** Use superpowers:executing-plans to implement this chunk.
> **Depends on:** Chunks 1–5

**Goal:** Prometheus adapter service fully functional. React UI scaffolded with all Phase 1 screens.

---

## Chunk 6a: Prometheus Adapter

### Task 6.1: Adapter Query Endpoint

**Files:**
- Create: `adapter-prometheus/app/router.py`
- Create: `adapter-prometheus/app/schemas.py`
- Create: `adapter-prometheus/app/prometheus_client.py`
- Create: `adapter-prometheus/tests/test_router.py`

- [ ] Write failing tests

```python
# adapter-prometheus/tests/test_router.py
import pytest
from httpx import AsyncClient, ASGITransport
from pytest_httpx import HTTPXMock

from app.main import app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_health(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_query_substitutes_variables(
    client: AsyncClient, httpx_mock: HTTPXMock
) -> None:
    # Mock Prometheus instant query response
    httpx_mock.add_response(
        url__startswith="http://localhost:9090/api/v1/query",
        json={
            "status": "success",
            "data": {"resultType": "vector", "result": [{"value": [1710000000, "450.3"]}]},
        },
    )
    sli_yaml = """spec_version: '1.0'
indicators:
  cpu: 'avg_over_time(cpu{instance="$vm_ip"}[5m])'
"""
    resp = await client.post("/query", json={
        "indicators": ["cpu"],
        "start": "2026-03-12T10:00:00Z",
        "end": "2026-03-12T10:30:00Z",
        "variables": {"vm_ip": "10.0.0.1"},
        "sli_yaml": sli_yaml,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "cpu" in data["metrics"]
    assert data["metrics"]["cpu"] == pytest.approx(450.3)


async def test_query_missing_indicator_returns_error(
    client: AsyncClient, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        url__startswith="http://localhost:9090",
        json={"status": "success", "data": {"resultType": "vector", "result": []}},
    )
    sli_yaml = "spec_version: '1.0'\nindicators:\n  missing_metric: 'empty_query()'\n"
    resp = await client.post("/query", json={
        "indicators": ["missing_metric"],
        "start": "2026-03-12T10:00:00Z",
        "end": "2026-03-12T10:30:00Z",
        "variables": {},
        "sli_yaml": sli_yaml,
    })
    assert resp.status_code == 200
    assert "missing_metric" in resp.json()["errors"]


async def test_query_unresolved_variable_returns_422(client: AsyncClient) -> None:
    sli_yaml = "spec_version: '1.0'\nindicators:\n  cpu: 'cpu{instance=\"$unset\"}'\n"
    resp = await client.post("/query", json={
        "indicators": ["cpu"],
        "start": "2026-03-12T10:00:00Z",
        "end": "2026-03-12T10:30:00Z",
        "variables": {},
        "sli_yaml": sli_yaml,
    })
    assert resp.status_code == 422
```

- [ ] Create `app/schemas.py`

```python
# adapter-prometheus/app/schemas.py
from __future__ import annotations
from pydantic import BaseModel


class QueryRequest(BaseModel):
    indicators: list[str]
    start: str
    end: str
    variables: dict[str, str] = {}
    sli_yaml: str


class QueryResponse(BaseModel):
    metrics: dict[str, float | None] = {}
    errors: dict[str, str] = {}
```

- [ ] Create `app/prometheus_client.py`

```python
# adapter-prometheus/app/prometheus_client.py
from __future__ import annotations

import re
from datetime import datetime

import httpx
import structlog
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import get_settings

logger = structlog.get_logger()
_VAR_RE = re.compile(r"\$([a-zA-Z_][a-zA-Z0-9_]*)")


def substitute(template: str, variables: dict[str, str]) -> str:
    def replace(m: re.Match[str]) -> str:
        name = m.group(1)
        if name not in variables:
            raise ValueError(f"Unresolved variable: ${name}")
        return variables[name]
    return _VAR_RE.sub(replace, template)


async def query_scalar(
    query: str,
    end: str,
    timeout: int,
    retry_attempts: int,
    retry_backoff: int,
) -> float | None:
    """Execute a PromQL instant query at `end` time and return single scalar."""
    settings = get_settings()
    url = f"{settings.prometheus_url}/api/v1/query"
    ts = datetime.fromisoformat(end.replace("Z", "+00:00")).timestamp()

    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(retry_attempts),
        wait=wait_exponential(multiplier=retry_backoff, min=1, max=30),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
        reraise=True,
    ):
        with attempt:
            auth = None
            s = settings
            if s.username:
                auth = (s.username, s.password.get_secret_value())
            async with httpx.AsyncClient(timeout=timeout, auth=auth) as client:
                resp = await client.get(url, params={"query": query, "time": ts})
                resp.raise_for_status()
                data = resp.json()

    if data["status"] != "success":
        return None
    results = data["data"]["result"]
    if not results:
        return None
    try:
        return float(results[0]["value"][1])
    except (IndexError, KeyError, ValueError):
        return None
```

- [ ] Create `app/router.py`

```python
# adapter-prometheus/app/router.py
from __future__ import annotations

import asyncio

import structlog
import yaml
from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.prometheus_client import query_scalar, substitute
from app.schemas import QueryRequest, QueryResponse

router = APIRouter()
logger = structlog.get_logger()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "datasource": "prometheus"}


@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest) -> QueryResponse:
    settings = get_settings()

    # Parse SLI YAML to get indicator→query map
    try:
        sli_data = yaml.safe_load(req.sli_yaml) or {}
        indicators_map: dict[str, str] = sli_data.get("indicators", {})
    except yaml.YAMLError as e:
        raise HTTPException(422, f"Invalid sli_yaml: {e}") from e

    # Apply variable substitution
    try:
        resolved_queries = {
            name: substitute(query, req.variables)
            for name, query in indicators_map.items()
            if name in req.indicators
        }
    except ValueError as e:
        raise HTTPException(422, str(e)) from e

    # Execute queries with concurrency limit
    sem = asyncio.Semaphore(10)
    metrics: dict[str, float | None] = {}
    errors: dict[str, str] = {}

    async def execute_one(name: str, promql: str) -> None:
        async with sem:
            try:
                value = await query_scalar(
                    promql,
                    req.end,
                    timeout=settings.timeout_seconds,
                    retry_attempts=settings.retry_attempts,
                    retry_backoff=settings.retry_backoff_seconds,
                )
                if value is None:
                    errors[name] = "no data in time range"
                else:
                    metrics[name] = value
            except Exception as exc:
                logger.warning("Indicator query failed", indicator=name, error=str(exc))
                errors[name] = str(exc)

    await asyncio.gather(*[execute_one(n, q) for n, q in resolved_queries.items()])
    return QueryResponse(metrics=metrics, errors=errors)
```

- [ ] Update `app/main.py`

```python
# adapter-prometheus/app/main.py
from fastapi import FastAPI
from app.router import router

app = FastAPI(title="Prometheus Adapter", version="0.1.0")
app.include_router(router)
```

- [ ] Run tests

```bash
cd adapter-prometheus
uv run pytest tests/ -v
```

- [ ] Commit

```bash
git add .
git commit -m "feat: Prometheus adapter with PromQL query, variable substitution, per-indicator retry"
```

---

## Chunk 6b: React UI Scaffold

### Task 6.2: UI Project Setup

**Files:**
- Create: `ui/` — Vite + React + TypeScript project

- [ ] Scaffold with Vite

```bash
cd ..
npm create vite@latest ui -- --template react-ts
cd ui
npm install
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
npm install recharts @tanstack/react-query axios react-router-dom
npm install -D @types/react-router-dom
```

- [ ] Configure Tailwind in `tailwind.config.ts`

```typescript
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: { extend: {} },
  plugins: [],
}
```

- [ ] Add to `src/index.css`

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] Create `src/api/client.ts`

```typescript
import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8080'

export const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
})
```

- [ ] Create `src/types/evaluation.ts`

```typescript
export interface IndicatorResult {
  metric: string
  display_name: string
  value: number | null
  compared_value: number | null
  change_relative_pct: number | null
  status: 'pass' | 'warning' | 'fail' | 'info' | 'error'
  score: number
  weight: number
  key_sli: boolean
  pass_targets: { criteria: string; target_value: number; violated: boolean }[]
  warning_targets: { criteria: string; target_value: number; violated: boolean }[] | null
}

export interface Annotation {
  id: string
  evaluation_id: string
  content: string
  author: string | null
  category: string | null
  meta: Record<string, unknown>
  created_at: string
}

export interface Evaluation {
  id: string
  name: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'partial'
  result: 'pass' | 'warning' | 'fail' | 'error' | null
  score: number | null
  start: string
  end: string
  slo_name: string | null
  slo_version: number | null
  ingestion_mode: string
  invalidated: boolean
  invalidation_note: string | null
  asset_snapshot: Record<string, unknown>
  metadata: Record<string, unknown>
  indicator_results: IndicatorResult[]
  annotations: Annotation[]
  job_stats: Record<string, unknown>
  created_at: string
}

export interface TrendPoint {
  timestamp: string
  value: number
  eval_id: string
  result: string
}
```

- [ ] Create `src/api/evaluations.ts`

```typescript
import { api } from './client'
import type { Evaluation, TrendPoint } from '../types/evaluation'

export const evaluationsApi = {
  list: (params: Record<string, string | number | undefined>) =>
    api.get<Evaluation[]>('/evaluations', { params }).then(r => r.data),

  get: (id: string) =>
    api.get<Evaluation>(`/evaluations/${id}`).then(r => r.data),

  invalidate: (id: string, payload: { invalidated: boolean; invalidation_note?: string }) =>
    api.patch<Evaluation>(`/evaluations/${id}`, payload).then(r => r.data),

  rerun: (id: string, payload: { mode: 'soft' | 'hard'; reason: string }) =>
    api.post(`/evaluations/${id}/rerun`, payload).then(r => r.data),

  addAnnotation: (id: string, payload: { content: string; author?: string; category?: string }) =>
    api.post(`/evaluations/${id}/annotations`, payload).then(r => r.data),

  deleteAnnotation: (evalId: string, annId: string) =>
    api.delete(`/evaluations/${evalId}/annotations/${annId}`),

  trend: (params: Record<string, string | undefined>) =>
    api.get<TrendPoint[]>('/trend', { params }).then(r => r.data),
}
```

- [ ] Commit

```bash
git add ui/
git commit -m "feat: React UI scaffold with Vite, Tailwind, TanStack Query, Recharts"
```

---

### Task 6.3: Evaluation List + Heatmap

**Files:**
- Create: `ui/src/pages/EvaluationsPage.tsx`
- Create: `ui/src/components/EvaluationList/EvaluationHeatmap.tsx`
- Create: `ui/src/components/EvaluationList/EvaluationTable.tsx`

- [ ] Create `EvaluationHeatmap.tsx`

```tsx
// src/components/EvaluationList/EvaluationHeatmap.tsx
import type { Evaluation } from '../../types/evaluation'

interface Props {
  evaluations: Evaluation[]
  onSelect: (e: Evaluation) => void
}

const RESULT_COLORS: Record<string, string> = {
  pass: 'bg-green-500',
  warning: 'bg-yellow-400',
  fail: 'bg-red-500',
  error: 'bg-gray-400',
}

export function EvaluationHeatmap({ evaluations, onSelect }: Props) {
  // Group by test name
  const byName = evaluations.reduce<Record<string, Evaluation[]>>((acc, e) => {
    ;(acc[e.name] ??= []).push(e)
    return acc
  }, {})

  return (
    <div className="overflow-x-auto">
      {Object.entries(byName).map(([name, evals]) => (
        <div key={name} className="flex items-center gap-2 mb-2">
          <span className="w-48 text-sm font-mono truncate">{name}</span>
          <div className="flex gap-1">
            {evals.map((e, i) => (
              <button
                key={e.id}
                title={`${e.result ?? e.status} | score: ${e.score?.toFixed(1) ?? '?'} | ${new Date(e.created_at).toLocaleDateString()}`}
                onClick={() => onSelect(e)}
                className={[
                  'w-6 h-6 rounded text-xs relative',
                  e.invalidated ? 'opacity-30' : '',
                  RESULT_COLORS[e.result ?? 'error'] ?? 'bg-gray-300',
                ].join(' ')}
              >
                {e.annotations?.length > 0 && (
                  <span className="absolute -top-1 -right-1 text-blue-700 text-xs">⚑</span>
                )}
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
```

- [ ] Create `EvaluationsPage.tsx`

```tsx
// src/pages/EvaluationsPage.tsx
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { evaluationsApi } from '../api/evaluations'
import { EvaluationHeatmap } from '../components/EvaluationList/EvaluationHeatmap'
import type { Evaluation } from '../types/evaluation'

export function EvaluationsPage() {
  const [selectedName, setSelectedName] = useState<string>('')
  const [selectedEval, setSelectedEval] = useState<Evaluation | null>(null)

  const { data = [], isLoading } = useQuery({
    queryKey: ['evaluations', selectedName],
    queryFn: () => evaluationsApi.list({ name: selectedName || undefined, limit: 100 }),
  })

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">Evaluations</h1>
      <input
        className="border px-3 py-1 rounded mb-4 w-64"
        placeholder="Filter by test name..."
        value={selectedName}
        onChange={e => setSelectedName(e.target.value)}
      />
      {isLoading ? (
        <p>Loading...</p>
      ) : (
        <EvaluationHeatmap evaluations={data} onSelect={setSelectedEval} />
      )}
      {selectedEval && (
        <div className="mt-4 text-sm text-gray-600">
          Selected: {selectedEval.id} — <a href={`/evaluations/${selectedEval.id}`} className="text-blue-600 underline">View detail →</a>
        </div>
      )}
    </div>
  )
}
```

- [ ] Commit

```bash
git add ui/src/
git commit -m "feat: evaluation list page with heatmap and annotation flags"
```

---

### Task 6.4: Evaluation Detail + SLI Breakdown

**Files:**
- Create: `ui/src/pages/EvaluationDetailPage.tsx`
- Create: `ui/src/components/EvaluationDetail/SliBreakdown.tsx`
- Create: `ui/src/components/EvaluationDetail/AnnotationPanel.tsx`
- Create: `ui/src/components/EvaluationDetail/InvalidateModal.tsx`

- [ ] Create `SliBreakdown.tsx`

```tsx
// src/components/EvaluationDetail/SliBreakdown.tsx
import type { IndicatorResult } from '../../types/evaluation'

const STATUS_COLORS: Record<string, string> = {
  pass: 'text-green-600',
  warning: 'text-yellow-600',
  fail: 'text-red-600',
  info: 'text-gray-500',
  error: 'text-gray-400',
}

interface Props {
  indicators: IndicatorResult[]
}

export function SliBreakdown({ indicators }: Props) {
  const sorted = [...indicators].sort((a, b) => {
    const order = { fail: 0, warning: 1, pass: 2, info: 3, error: 4 }
    return (order[a.status] ?? 9) - (order[b.status] ?? 9)
  })

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="bg-gray-100 text-left">
            <th className="px-3 py-2">Metric</th>
            <th className="px-3 py-2">Value</th>
            <th className="px-3 py-2">Baseline</th>
            <th className="px-3 py-2">Change %</th>
            <th className="px-3 py-2">Status</th>
            <th className="px-3 py-2">Score</th>
            <th className="px-3 py-2">Weight</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map(ir => (
            <tr key={ir.metric} className="border-b hover:bg-gray-50">
              <td className="px-3 py-2 font-mono">
                {ir.key_sli && <span title="Key SLI" className="text-red-500 mr-1">★</span>}
                {ir.display_name || ir.metric}
              </td>
              <td className="px-3 py-2">{ir.value?.toFixed(2) ?? '—'}</td>
              <td className="px-3 py-2">{ir.compared_value?.toFixed(2) ?? '—'}</td>
              <td className="px-3 py-2">
                {ir.change_relative_pct != null
                  ? `${ir.change_relative_pct > 0 ? '+' : ''}${ir.change_relative_pct.toFixed(1)}%`
                  : '—'}
              </td>
              <td className={`px-3 py-2 font-semibold ${STATUS_COLORS[ir.status]}`}>
                {ir.status.toUpperCase()}
              </td>
              <td className="px-3 py-2">{ir.score.toFixed(1)}</td>
              <td className="px-3 py-2">{ir.weight}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
```

- [ ] Create `InvalidateModal.tsx`

```tsx
// src/components/EvaluationDetail/InvalidateModal.tsx
import { useState } from 'react'

interface Props {
  isInvalidated: boolean
  onConfirm: (note: string) => void
  onClose: () => void
}

export function InvalidateModal({ isInvalidated, onConfirm, onClose }: Props) {
  const [note, setNote] = useState('')
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-96 shadow-xl">
        <h2 className="text-lg font-bold mb-3">
          {isInvalidated ? 'Un-invalidate' : 'Invalidate'} Evaluation
        </h2>
        {!isInvalidated && (
          <textarea
            className="w-full border rounded p-2 mb-4 text-sm"
            rows={4}
            placeholder="Reason for invalidation..."
            value={note}
            onChange={e => setNote(e.target.value)}
          />
        )}
        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="px-4 py-2 border rounded text-sm">Cancel</button>
          <button
            onClick={() => onConfirm(note)}
            className="px-4 py-2 bg-red-600 text-white rounded text-sm"
          >
            Confirm
          </button>
        </div>
      </div>
    </div>
  )
}
```

- [ ] Create `AnnotationPanel.tsx`

```tsx
// src/components/EvaluationDetail/AnnotationPanel.tsx
import { useState } from 'react'
import type { Annotation } from '../../types/evaluation'

interface Props {
  annotations: Annotation[]
  onAdd: (content: string, category?: string) => void
  onDelete: (id: string) => void
}

export function AnnotationPanel({ annotations, onAdd, onDelete }: Props) {
  const [content, setContent] = useState('')
  const [category, setCategory] = useState('')

  return (
    <div>
      <h3 className="font-semibold mb-2">Annotations</h3>
      <ul className="space-y-2 mb-4">
        {annotations.map(a => (
          <li key={a.id} className="border rounded p-3 text-sm">
            <div className="flex justify-between">
              <span className="font-mono text-xs text-gray-500">{a.category ?? 'general'}</span>
              <button onClick={() => onDelete(a.id)} className="text-red-400 text-xs">×</button>
            </div>
            <p className="mt-1">{a.content}</p>
            <p className="text-xs text-gray-400 mt-1">
              {a.author} · {new Date(a.created_at).toLocaleString()}
            </p>
          </li>
        ))}
        {annotations.length === 0 && <li className="text-sm text-gray-400">No annotations yet.</li>}
      </ul>
      <div className="flex gap-2">
        <input
          className="border rounded px-2 py-1 text-sm w-32"
          placeholder="category"
          value={category}
          onChange={e => setCategory(e.target.value)}
        />
        <input
          className="border rounded px-2 py-1 text-sm flex-1"
          placeholder="Add annotation..."
          value={content}
          onChange={e => setContent(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' && content) {
              onAdd(content, category || undefined)
              setContent('')
              setCategory('')
            }
          }}
        />
        <button
          onClick={() => { if (content) { onAdd(content, category || undefined); setContent(''); setCategory('') } }}
          className="bg-blue-600 text-white px-3 rounded text-sm"
        >Add</button>
      </div>
    </div>
  )
}
```

- [ ] Create `EvaluationDetailPage.tsx`

```tsx
// src/pages/EvaluationDetailPage.tsx
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { evaluationsApi } from '../api/evaluations'
import { SliBreakdown } from '../components/EvaluationDetail/SliBreakdown'
import { AnnotationPanel } from '../components/EvaluationDetail/AnnotationPanel'
import { InvalidateModal } from '../components/EvaluationDetail/InvalidateModal'

const RESULT_BG: Record<string, string> = {
  pass: 'bg-green-100 text-green-800',
  warning: 'bg-yellow-100 text-yellow-800',
  fail: 'bg-red-100 text-red-800',
}

export function EvaluationDetailPage() {
  const { id } = useParams<{ id: string }>()
  const qc = useQueryClient()
  const [showInvalidate, setShowInvalidate] = useState(false)

  const { data: ev, isLoading } = useQuery({
    queryKey: ['evaluation', id],
    queryFn: () => evaluationsApi.get(id!),
    refetchInterval: (data) => data?.status === 'completed' ? false : 3000,
  })

  const invalidateMut = useMutation({
    mutationFn: (note: string) =>
      evaluationsApi.invalidate(id!, { invalidated: !ev?.invalidated, invalidation_note: note }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['evaluation', id] }); setShowInvalidate(false) },
  })

  const addAnnotation = useMutation({
    mutationFn: ({ content, category }: { content: string; category?: string }) =>
      evaluationsApi.addAnnotation(id!, { content, category }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['evaluation', id] }),
  })

  const deleteAnnotation = useMutation({
    mutationFn: (annId: string) => evaluationsApi.deleteAnnotation(id!, annId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['evaluation', id] }),
  })

  if (isLoading || !ev) return <p className="p-6">Loading...</p>

  const isPending = ev.status !== 'completed'

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center gap-4 mb-6">
        <h1 className="text-2xl font-bold font-mono">{ev.name}</h1>
        {ev.result && (
          <span className={`px-3 py-1 rounded-full text-sm font-semibold ${RESULT_BG[ev.result] ?? 'bg-gray-100'}`}>
            {ev.result.toUpperCase()} {ev.score?.toFixed(1)}%
          </span>
        )}
        {isPending && <span className="text-sm text-gray-500 animate-pulse">{ev.status}...</span>}
        {ev.invalidated && <span className="text-xs text-gray-400 border px-2 py-1 rounded">INVALIDATED</span>}
      </div>

      <div className="text-sm text-gray-500 mb-4">
        SLO: {ev.slo_name ?? 'inline'} {ev.slo_version ? `v${ev.slo_version}` : ''} ·
        {new Date(ev.start).toLocaleString()} → {new Date(ev.end).toLocaleString()}
      </div>

      {!isPending && <SliBreakdown indicators={ev.indicator_results} />}

      <div className="mt-6 flex gap-3">
        <button
          onClick={() => setShowInvalidate(true)}
          className="px-4 py-2 border border-red-300 text-red-600 rounded text-sm"
        >
          {ev.invalidated ? 'Un-invalidate' : 'Invalidate'}
        </button>
      </div>

      <div className="mt-8">
        <AnnotationPanel
          annotations={ev.annotations}
          onAdd={(content, category) => addAnnotation.mutate({ content, category })}
          onDelete={(annId) => deleteAnnotation.mutate(annId)}
        />
      </div>

      {showInvalidate && (
        <InvalidateModal
          isInvalidated={ev.invalidated}
          onConfirm={(note) => invalidateMut.mutate(note)}
          onClose={() => setShowInvalidate(false)}
        />
      )}
    </div>
  )
}
```

- [ ] Commit

```bash
git add ui/src/
git commit -m "feat: evaluation detail page with SLI breakdown, annotations, invalidation"
```

---

### Task 6.5: Trend Chart + SLO Manager + App Router

**Files:**
- Create: `ui/src/pages/TrendPage.tsx`
- Create: `ui/src/components/TrendChart/TrendChart.tsx`
- Create: `ui/src/pages/SloManagerPage.tsx`
- Create: `ui/src/App.tsx`
- Create: `ui/Dockerfile`
- Create: `ui/nginx.conf`

- [ ] Create `TrendChart.tsx`

```tsx
// src/components/TrendChart/TrendChart.tsx
import { useState } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from 'recharts'
import type { TrendPoint } from '../../types/evaluation'

interface Props {
  data: TrendPoint[]
  metricName: string
  passThreshold?: number
  warningThreshold?: number
}

export function TrendChart({ data, metricName, passThreshold, warningThreshold }: Props) {
  const values = data.map(d => d.value).filter(Boolean) as number[]
  const defaultMin = values.length ? Math.min(...values) * 0.9 : 0
  const defaultMax = values.length ? Math.max(...values) * 1.1 : 100

  const [yMin, setYMin] = useState(defaultMin.toFixed(1))
  const [yMax, setYMax] = useState(defaultMax.toFixed(1))

  const POINT_COLOR: Record<string, string> = {
    pass: '#22c55e', warning: '#eab308', fail: '#ef4444',
  }

  return (
    <div>
      <h3 className="font-mono text-sm mb-2">{metricName}</h3>
      <div className="flex gap-3 items-center mb-2 text-xs">
        <label>Y min: <input className="border rounded px-1 w-20" value={yMin} onChange={e => setYMin(e.target.value)} /></label>
        <label>Y max: <input className="border rounded px-1 w-20" value={yMax} onChange={e => setYMax(e.target.value)} /></label>
      </div>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data} margin={{ left: 10, right: 10 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="timestamp" tickFormatter={v => new Date(v).toLocaleDateString()} tick={{ fontSize: 11 }} />
          <YAxis domain={[parseFloat(yMin), parseFloat(yMax)]} tick={{ fontSize: 11 }} />
          <Tooltip formatter={(v: number) => v.toFixed(3)} />
          {passThreshold && <ReferenceLine y={passThreshold} stroke="#22c55e" strokeDasharray="4 4" label={{ value: 'pass', fontSize: 10 }} />}
          {warningThreshold && <ReferenceLine y={warningThreshold} stroke="#eab308" strokeDasharray="4 4" label={{ value: 'warn', fontSize: 10 }} />}
          <Line
            type="monotone"
            dataKey="value"
            stroke="#3b82f6"
            dot={(props: any) => {
              const color = POINT_COLOR[props.payload.result] ?? '#94a3b8'
              return <circle key={props.key} cx={props.cx} cy={props.cy} r={4} fill={color} stroke="white" strokeWidth={1} />
            }}
            strokeWidth={2}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
```

- [ ] Create `TrendPage.tsx`

```tsx
// src/pages/TrendPage.tsx
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { evaluationsApi } from '../api/evaluations'
import { TrendChart } from '../components/TrendChart/TrendChart'

export function TrendPage() {
  const [testName, setTestName] = useState('')
  const [metric, setMetric] = useState('')

  const { data = [] } = useQuery({
    queryKey: ['trend', testName, metric],
    queryFn: () => evaluationsApi.trend({ test_name: testName, metric }),
    enabled: !!(testName && metric),
  })

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">Metric Trend</h1>
      <div className="flex gap-3 mb-6">
        <input className="border rounded px-3 py-1" placeholder="Test name" value={testName} onChange={e => setTestName(e.target.value)} />
        <input className="border rounded px-3 py-1" placeholder="Metric name" value={metric} onChange={e => setMetric(e.target.value)} />
      </div>
      {data.length > 0 ? (
        <TrendChart data={data} metricName={metric} />
      ) : (
        <p className="text-gray-400 text-sm">Enter test name and metric to see trend.</p>
      )}
    </div>
  )
}
```

- [ ] Create basic `SloManagerPage.tsx`

```tsx
// src/pages/SloManagerPage.tsx
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'

interface SLOVersion { name: string; version: number; notes: string | null; author: string | null; created_at: string }

export function SloManagerPage() {
  const qc = useQueryClient()
  const [name, setName] = useState('')
  const [yaml, setYaml] = useState('')
  const [notes, setNotes] = useState('')

  const { data: slos = [] } = useQuery({
    queryKey: ['slos'],
    queryFn: () => api.get<SLOVersion[]>('/slos').then(r => r.data),
  })

  const createMut = useMutation({
    mutationFn: () => api.post('/slos', { name, slo_yaml: yaml, notes }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['slos'] }); setName(''); setYaml(''); setNotes('') },
  })

  return (
    <div className="p-6 max-w-4xl">
      <h1 className="text-2xl font-bold mb-4">SLO Manager</h1>

      <table className="w-full text-sm border-collapse mb-8">
        <thead><tr className="bg-gray-100"><th className="px-3 py-2 text-left">Name</th><th>Version</th><th>Author</th><th>Notes</th><th>Created</th></tr></thead>
        <tbody>
          {slos.map(s => (
            <tr key={`${s.name}-${s.version}`} className="border-b">
              <td className="px-3 py-2 font-mono">{s.name}</td>
              <td className="px-3 py-2 text-center">v{s.version}</td>
              <td className="px-3 py-2">{s.author}</td>
              <td className="px-3 py-2 text-gray-500">{s.notes}</td>
              <td className="px-3 py-2">{new Date(s.created_at).toLocaleDateString()}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2 className="font-semibold mb-2">Register / Update SLO</h2>
      <div className="flex flex-col gap-2">
        <input className="border rounded px-3 py-1" placeholder="SLO name" value={name} onChange={e => setName(e.target.value)} />
        <textarea className="border rounded px-3 py-2 font-mono text-xs" rows={10} placeholder="SLO YAML..." value={yaml} onChange={e => setYaml(e.target.value)} />
        <input className="border rounded px-3 py-1" placeholder="Notes (optional)" value={notes} onChange={e => setNotes(e.target.value)} />
        <button onClick={() => createMut.mutate()} className="bg-blue-600 text-white px-4 py-2 rounded">Save</button>
      </div>
    </div>
  )
}
```

- [ ] Create `App.tsx`

```tsx
// src/App.tsx
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { EvaluationsPage } from './pages/EvaluationsPage'
import { EvaluationDetailPage } from './pages/EvaluationDetailPage'
import { TrendPage } from './pages/TrendPage'
import { SloManagerPage } from './pages/SloManagerPage'

const qc = new QueryClient()

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <nav className="flex gap-6 px-6 py-3 bg-gray-900 text-white text-sm">
          <Link to="/" className="hover:underline">Evaluations</Link>
          <Link to="/trend" className="hover:underline">Trend</Link>
          <Link to="/slos" className="hover:underline">SLOs</Link>
        </nav>
        <Routes>
          <Route path="/" element={<EvaluationsPage />} />
          <Route path="/evaluations/:id" element={<EvaluationDetailPage />} />
          <Route path="/trend" element={<TrendPage />} />
          <Route path="/slos" element={<SloManagerPage />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
```

- [ ] Create `Dockerfile` for UI

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

- [ ] Create `nginx.conf`

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://quality-gate-api:8080/;
        proxy_set_header Host $host;
    }
}
```

- [ ] Build and verify UI

```bash
npm run build
```

Expected: `dist/` folder created with no errors.

- [ ] Commit

```bash
git add .
git commit -m "feat: complete React UI with heatmap, detail, trend chart, SLO manager, Docker"
```

---

## Final Task: End-to-End Smoke Test

- [ ] Start all services

```bash
cd ..
docker compose up --build -d
docker compose ps
```

Expected: all services `running` or `healthy`.

- [ ] Run smoke test

```bash
# Create an SLO
curl -s -X POST http://localhost:8080/slos \
  -H "Content-Type: application/json" \
  -d '{"name":"smoke-slo","slo_yaml":"spec_version: '"'"'1.0'"'"'\nindicators:\n  latency: '"'"'metric()'"'"'\nobjectives:\n  - sli: latency\n    pass:\n      - criteria: [\"<1000\"]\n    weight: 1\ntotal_score:\n  pass: \"90%\"\n  warning: \"75%\"\n"}' | jq .version

# Trigger push-mode evaluation
curl -s -X POST http://localhost:8080/evaluations \
  -H "Content-Type: application/json" \
  -d '{"name":"smoke-test","start":"2026-03-12T10:00:00Z","end":"2026-03-12T10:30:00Z","slo_name":"smoke-slo","metrics":{"latency":450.0},"metadata":{"os":"linux"}}' | jq .eval_id

# Wait 2 seconds, get result
sleep 2
curl -s http://localhost:8080/evaluations/<eval_id_from_above> | jq '{result,score,status}'
```

Expected: `{"result":"pass","score":100.0,"status":"completed"}`

- [ ] Open UI in browser

```
http://localhost:3000
```

Expected: Evaluations page loads, heatmap shows the smoke test evaluation.

- [ ] Commit

```bash
git commit -m "chore: Phase 1 implementation complete — all services running" --allow-empty
```
