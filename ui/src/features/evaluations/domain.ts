// ui/src/features/evaluations/domain.ts
//
// Domain types for the evaluations feature. Hand-written in UI vocabulary.
// Components import from here (via the barrel at './index.ts'), never from
// '@/generated/api'. DTO → domain conversion lives in './mappers.ts' and runs
// inside fetch functions in './api.ts'.
//
// Period note: period is modelled as DateRange ({from, to} ISO strings), not
// a pair of Date objects. period.from is used as a Map/Set key in
// EvaluationHeatmap, the same constraint that keeps navigator on ISO strings
// (see features/navigator/domain.ts, commit ce34376).

import type { DateRange } from '@/lib/dateRange'

// Canonical outcome union. The backend emits `result: string | null` plus a
// separate `invalidated: boolean` flag; the mapper collapses that pair into a
// single value — `invalidated: true` wins over `result`. `null` / '' map to
// 'error' so cell colouring degrades gracefully.
export type Outcome = 'pass' | 'warning' | 'fail' | 'error' | 'invalidated'

export interface AssetSnapshot {
  name: string
  displayName: string | null
  tags: Record<string, string>
  primaryVersion: string | null
  buildRef: string | null
}

export interface BaselinePin {
  author: string
  reason: string
  pinnedAt: Date
  unpinnedAt: Date | null
}

export interface Annotation {
  id: string
  sloEvaluationId: string | null
  evaluationRunId: string | null
  content: string
  author: string | null
  category: string | null
  tags: Record<string, unknown>
  noteGroupId: string | null
  noteGroupName: string | null
  hiddenAt: Date | null
  hiddenBy: string | null
  hiddenReason: string | null
  createdAt: Date
  updatedAt: Date | null
}

export interface FailingIndicator {
  metric: string
  displayName: string
  value: number | null
  threshold: string
}

export interface PassTarget {
  criteria: string
  targetValue: number
  violated: boolean
}

export interface Indicator {
  metric: string
  displayName: string
  tabGroup: string | null
  value: number | null
  comparedValue: number | null
  changeAbsolute: number | null
  changeRelativePct: number | null
  aggregation: string | null
  status: 'pass' | 'warning' | 'fail'
  score: number
  weight: number
  keySli: boolean
  passTargets: PassTarget[]
  warningTargets: PassTarget[]
}

export interface SliMetadata {
  mode: 'aggregated'
  expectedSamples: number
  actualSamples: number
  missingPct: number
  chunksFailed: number
}

// Evaluation (shared fields between list and detail views). The domain uses
// one type for both shapes and a narrower `EvaluationDetail extends Evaluation`
// for fields only present on the detail endpoint, mirroring navigator's
// approach of one canonical domain entity per feature.
export interface Evaluation {
  id: string
  evaluationId: string
  evaluationName: string
  status: string
  outcome: Outcome
  score: number | null
  period: DateRange
  sloName: string | null
  sloVersion: number | null
  sliName: string | null
  sliVersion: number | null
  dataSourceName: string | null
  ingestionMode: string
  adapterUsed: string | null
  invalidated: boolean
  originalOutcome: Outcome | null
  originalScore: number | null
  overrideReason: string | null
  overrideAuthor: string | null
  assetSnapshot: AssetSnapshot
  variables: Record<string, string>
  baselinePin: BaselinePin | null
  latestAnnotation: Annotation | null
  annotationCount: number
  createdAt: Date
  topFailures: FailingIndicator[]
}

export interface EvaluationDetail extends Evaluation {
  invalidationNote: string | null
  comparedEvaluationIds: string[]
  annotations: Annotation[]
  indicators: Indicator[]
  totalScorePassThreshold: number | null
  totalScoreWarningThreshold: number | null
  sliMetadata: Record<string, SliMetadata>
}

export interface EvaluationList {
  items: Evaluation[]
  total: number
  truncated: boolean
}

// --- Trend ---

export interface TrendTargetEntry {
  criteria: string
  targetValue: number
  violated: boolean
}

export interface TrendTargets {
  pass: TrendTargetEntry[]
  warn: TrendTargetEntry[]
}

export interface TrendPoint {
  timestamp: Date
  value: number
  score: number
  evalId: string
  outcome: Outcome
  baseline: number | null
  evaluationName: string | null
  targets: TrendTargets | null
}

// --- Re-evaluation ---

// Domain re-evaluation mode — discriminated union. Backend flattens to
// from_baseline / from_date / from_evaluation_id on the wire.
export type ReEvaluateMode =
  | { kind: 'baseline' }
  | { kind: 'date'; fromDate: string }
  | { kind: 'evaluation'; fromEvaluationId: string }

export interface ReEvaluateInput {
  assetName: string
  sloName: string | null
  mode: ReEvaluateMode
  sloVersion: number | null
  dryRun: boolean
  pinStrategy: 'skip_to_pin' | 'ignore_pin' | null
}

export interface ReEvaluateResultItem {
  id: string
  evaluationName: string
  sloName: string
  sloVersion: number
  period: DateRange
  oldOutcome: Outcome
  newOutcome: Outcome
  oldScore: number
  newScore: number
}

export interface ReEvaluateResponse {
  affectedEvaluations: number
  sloVersionUsed: number | null
  results: ReEvaluateResultItem[]
}

export interface PinConflictInfo {
  pinDate: string
  pinEvaluationId: string
}

// --- Trigger / override / pin write-path inputs ---

export interface TriggerEvaluationInput {
  assetName: string
  evalName: string
  period: DateRange
  variables: Record<string, string>
}

export interface OverrideStatusInput {
  outcome: Outcome
  reason: string
  author: string
}

// --- Misc read-only endpoints ---

export interface EvaluationNameEntry {
  name: string
  count: number
  lastRun: Date
}

export interface EvaluationFilters {
  groupName?: string
  assetName?: string
  evaluationName?: string[]
  date?: string
  from?: string
  to?: string
}
