// src/lib/queryKeys.ts
// Centralised React Query key factory.
// Eliminates magic-string query keys scattered across components.
// Usage: useQuery({ queryKey: evaluationKeys.list(filters), queryFn: ... })
// EvaluationFilters canonical definition is in features/evaluations/types.ts.
// lib/ must not import from features/, so we use an inline structural type here.
// The shapes are identical — TypeScript's structural typing ensures compatibility.

type EvalFilters = { lab?: string; date?: string; slot?: string }

export const evaluationKeys = {
  all: ['evaluations'] as const,
  list: (filters: EvalFilters) => [...evaluationKeys.all, filters] as const,
  detail: (id: string) => [...evaluationKeys.all, id] as const,
  trend: (id: string, metric: string) => [...evaluationKeys.detail(id), metric] as const,
}

export const assetKeys = {
  all: ['assets'] as const,
  groups: () => [...assetKeys.all, 'groups'] as const,
}

export const sloKeys = {
  all: ['slos'] as const,
  detail: (name: string) => [...sloKeys.all, name] as const,
}

export const sliKeys = {
  all: ['sli-definitions'] as const,
  detail: (name: string) => [...sliKeys.all, name] as const,
  versions: (name: string) => [...sliKeys.detail(name), 'versions'] as const,
}

export const groupKeys = {
  all: ['asset-groups'] as const,
  tree: () => [...groupKeys.all, 'tree'] as const,
  detail: (name: string) => [...groupKeys.all, name] as const,
  links: (name: string) => [...groupKeys.detail(name), 'links'] as const,
}

export const datasourceKeys = {
  all: ['datasources'] as const,
}
