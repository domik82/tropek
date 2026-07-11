// src/lib/queryKeys.ts
// Centralised React Query key factory.
// Eliminates magic-string query keys scattered across components.
// Usage: useQuery({ queryKey: evaluationKeys.list(filters), queryFn: ... })
// EvaluationFilters canonical definition is in features/evaluations/types.ts.
// lib/ must not import from features/, so we use an inline structural type here.
// The shapes are identical — TypeScript's structural typing ensures compatibility.

type EvalFilters = {
  group_name?: string
  asset_name?: string
  evaluation_name?: string[]
  date?: string
  from?: string
  to?: string
}

export const evaluationKeys = {
  all: ['evaluations'] as const,
  list: (filters: EvalFilters) => [...evaluationKeys.all, filters] as const,
  detail: (id: string) => [...evaluationKeys.all, id] as const,
  allTrends: ['trend'] as const,
  trend: (assetName: string, sloName: string, metric: string, dateRange?: Record<string, string | undefined>) =>
    ['trend', assetName, sloName, metric, dateRange] as const,
  sloTrends: (assetName: string, sloName: string, dateRange?: Record<string, string | undefined>) =>
    ['slo-trends', assetName, sloName, dateRange] as const,
  allHeatmaps: ['metric-heatmap'] as const,
  heatmap: (assetName: string, filters?: Record<string, string | undefined>, evalNames?: string[]) =>
    evalNames?.length
      ? ['metric-heatmap', assetName, filters, evalNames] as const
      : ['metric-heatmap', assetName, filters] as const,
  allNames: ['evaluation-names'] as const,
  names: (scope: { asset_name?: string; group_name?: string }) =>
    ['evaluation-names', scope] as const,
  columnAnnotations: (evaluationId: string) =>
    [...evaluationKeys.all, 'column-annotations', evaluationId] as const,
}

export const assetKeys = {
  all: ['assets'] as const,
  groups: () => [...assetKeys.all, 'groups'] as const,
}

export const assetTypeKeys = {
  all: ['asset-types'] as const,
}

export const labelKeys = {
  keys: () => ['label-keys'] as const,
  values: (key: string) => ['label-values', key] as const,
}

export const sloKeys = {
  all: ['slos'] as const,
  detail: (name: string) => [...sloKeys.all, name] as const,
  tagKeys: () => [...sloKeys.all, 'tag-keys'] as const,
  tagValues: (key: string) => [...sloKeys.all, 'tag-values', key] as const,
}

export const sliKeys = {
  all: ['sli-definitions'] as const,
  detail: (name: string) => [...sliKeys.all, name] as const,
  versions: (name: string) => [...sliKeys.detail(name), 'versions'] as const,
  tagKeys: () => [...sliKeys.all, 'tag-keys'] as const,
  tagValues: (key: string) => [...sliKeys.all, 'tag-values', key] as const,
}

export const groupKeys = {
  all: ['asset-groups'] as const,
  tree: () => [...groupKeys.all, 'tree'] as const,
  detail: (name: string) => [...groupKeys.all, name] as const,
  links: (name: string) => [...groupKeys.detail(name), 'links'] as const,
  assignments: (name: string) => [...groupKeys.detail(name), 'assignments'] as const,
}

export const assignmentKeys = {
  all: ['slo-assignments'] as const,
  asset: (assetName: string) => [...assignmentKeys.all, 'asset', assetName] as const,
  group: (groupName: string) => [...assignmentKeys.all, 'group', groupName] as const,
}

export const datasourceKeys = {
  all: ['datasources'] as const,
  detail: (name: string) => [...datasourceKeys.all, name] as const,
  tagKeys: () => [...datasourceKeys.all, 'tag-keys'] as const,
  tagValues: (key: string) => [...datasourceKeys.all, 'tag-values', key] as const,
}

export const sloGroupKeys = {
  all: ['slo-groups'] as const,
  detail: (name: string) => [...sloGroupKeys.all, name] as const,
}
