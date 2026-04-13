// ui/src/features/evaluations/mappers.ts
//
// Mappers for the evaluations feature. One dtoToX per domain type on the read
// side; three xInputToDto reverse mappers on the write side per §11.3 of the
// UI layering spec. Mappers run inside api.ts fetch functions, once per
// network request, and React Query stores the domain type.

import type { components } from '@/generated/api'
import { makeDateRange } from '@/lib/dateRange'
import type {
  Annotation,
  AssetSnapshot,
  BaselinePin,
  Evaluation,
  EvaluationDetail,
  EvaluationList,
  EvaluationNameEntry,
  FailingIndicator,
  Indicator,
  Outcome,
  OverrideStatusInput,
  ReEvaluateInput,
  ReEvaluateResponse,
  SliMetadata,
  TrendPoint,
  TriggerEvaluationInput,
} from './domain'

// --- DTO aliases -----------------------------------------------------------

export type EvaluationSummaryDto = components['schemas']['EvaluationSummary']
export type EvaluationDetailDto = components['schemas']['EvaluationDetail']
export type AssetSnapshotDto = components['schemas']['AssetSnapshot']
export type AnnotationDto = components['schemas']['AnnotationRead']
export type IndicatorResultDto = components['schemas']['IndicatorResult']
export type PassTargetDto = components['schemas']['PassTarget']
export type FailingIndicatorDto = components['schemas']['FailingIndicator']
export type SliMetadataDto = components['schemas']['SliMetadata']
export type TrendPointDto = components['schemas']['TrendPoint']
export type TrendTargetsDto = components['schemas']['TrendTargets']
export type TrendTargetEntryDto = components['schemas']['TrendTargetEntry']
export type EvaluationNameEntryDto = components['schemas']['EvaluationNameEntry']
export type ReEvaluateRequestDto = components['schemas']['ReEvaluateRequest']
export type ReEvaluateResponseDto = components['schemas']['ReEvaluateResponse']
export type ReEvalResultItemDto = components['schemas']['ReEvalResultItem']
export type EvaluateSingleRequestDto = components['schemas']['EvaluateSingleRequest']
export type OverrideStatusRequestDto = components['schemas']['OverrideStatusRequest']
export type EvaluateSingleResponseDto = components['schemas']['EvaluateSingleResponse']

// --- Helpers --------------------------------------------------------------

function normalizeOutcome(raw: string | null | undefined): Outcome {
  switch (raw) {
    case 'pass':
    case 'warning':
    case 'fail':
    case 'error':
    case 'invalidated':
      return raw
    default:
      return 'error'
  }
}

// Collapse (result, invalidated) into a single Outcome value. See the
// `Outcome` comment in domain.ts for rationale.
function collapseOutcome(
  result: string | null | undefined,
  invalidated: boolean,
): Outcome {
  if (invalidated) return 'invalidated'
  return normalizeOutcome(result)
}

function dtoToAssetSnapshot(dto: AssetSnapshotDto): AssetSnapshot {
  return {
    name: dto.name,
    displayName: dto.display_name ?? null,
    tags: (dto.tags ?? {}) as Record<string, string>,
    primaryVersion: dto.primary_version ?? null,
    buildRef: dto.build_ref ?? null,
  }
}

function dtoToBaselinePin(dto: EvaluationSummaryDto | EvaluationDetailDto): BaselinePin | null {
  if (!dto.baseline_pinned_at) return null
  return {
    author: dto.baseline_pin_author ?? '',
    reason: dto.baseline_pin_reason ?? '',
    pinnedAt: new Date(dto.baseline_pinned_at),
    unpinnedAt: dto.baseline_unpinned_at ? new Date(dto.baseline_unpinned_at) : null,
  }
}

function dtoToFailingIndicator(dto: FailingIndicatorDto): FailingIndicator {
  return {
    metric: dto.metric,
    displayName: dto.display_name,
    value: dto.value ?? null,
    threshold: dto.threshold,
  }
}

function dtoToSliMetadata(dto: SliMetadataDto): SliMetadata {
  return {
    mode: dto.mode,
    expectedSamples: dto.expected_samples,
    actualSamples: dto.actual_samples,
    missingPct: dto.missing_pct,
    chunksFailed: dto.chunks_failed,
  }
}

// --- Exhaustiveness frames ------------------------------------------------

// EvaluationSummary
type DroppedEvaluationSummaryKeys = never
type MappedEvaluationSummaryKeys =
  | 'id'
  | 'evaluation_id'
  | 'evaluation_name'
  | 'status'
  | 'result'
  | 'score'
  | 'period_start'
  | 'period_end'
  | 'slo_name'
  | 'slo_version'
  | 'sli_name'
  | 'sli_version'
  | 'data_source_name'
  | 'ingestion_mode'
  | 'adapter_used'
  | 'invalidated'
  | 'original_result'
  | 'original_score'
  | 'override_reason'
  | 'override_author'
  | 'asset_snapshot'
  | 'variables'
  | 'latest_annotation'
  | 'annotation_count'
  | 'created_at'
  | 'top_failures'
  | 'baseline_pin_author'
  | 'baseline_pin_reason'
  | 'baseline_pinned_at'
  | 'baseline_unpinned_at'
type _EvaluationSummaryCoverage = Exclude<
  keyof EvaluationSummaryDto,
  MappedEvaluationSummaryKeys | DroppedEvaluationSummaryKeys
>
const _evaluationSummaryExhaustive: _EvaluationSummaryCoverage extends never
  ? true
  : _EvaluationSummaryCoverage = true
void _evaluationSummaryExhaustive

// EvaluationDetail (extends summary with detail-only fields)
type DroppedEvaluationDetailKeys = never
type MappedEvaluationDetailKeys =
  | MappedEvaluationSummaryKeys
  | 'invalidation_note'
  | 'compared_evaluation_ids'
  | 'annotations'
  | 'indicator_results'
  | 'total_score_pass_threshold'
  | 'total_score_warning_threshold'
  | 'sli_metadata'
type _EvaluationDetailCoverage = Exclude<
  keyof EvaluationDetailDto,
  MappedEvaluationDetailKeys | DroppedEvaluationDetailKeys
>
const _evaluationDetailExhaustive: _EvaluationDetailCoverage extends never
  ? true
  : _EvaluationDetailCoverage = true
void _evaluationDetailExhaustive

// IndicatorResult
type DroppedIndicatorKeys = never
type MappedIndicatorKeys =
  | 'metric'
  | 'display_name'
  | 'tab_group'
  | 'value'
  | 'compared_value'
  | 'change_absolute'
  | 'change_relative_pct'
  | 'aggregation'
  | 'status'
  | 'score'
  | 'weight'
  | 'key_sli'
  | 'pass_targets'
  | 'warning_targets'
type _IndicatorCoverage = Exclude<
  keyof IndicatorResultDto,
  MappedIndicatorKeys | DroppedIndicatorKeys
>
const _indicatorExhaustive: _IndicatorCoverage extends never
  ? true
  : _IndicatorCoverage = true
void _indicatorExhaustive

// AnnotationRead
type DroppedAnnotationKeys = never
type MappedAnnotationKeys =
  | 'id'
  | 'content'
  | 'author'
  | 'category'
  | 'tags'
  | 'hidden_at'
  | 'hidden_by'
  | 'hidden_reason'
  | 'created_at'
  | 'updated_at'
type _AnnotationCoverage = Exclude<
  keyof AnnotationDto,
  MappedAnnotationKeys | DroppedAnnotationKeys
>
const _annotationExhaustive: _AnnotationCoverage extends never
  ? true
  : _AnnotationCoverage = true
void _annotationExhaustive

// AssetSnapshot
type DroppedAssetSnapshotKeys = never
type MappedAssetSnapshotKeys =
  | 'name'
  | 'display_name'
  | 'tags'
  | 'primary_version'
  | 'build_ref'
type _AssetSnapshotCoverage = Exclude<
  keyof AssetSnapshotDto,
  MappedAssetSnapshotKeys | DroppedAssetSnapshotKeys
>
const _assetSnapshotExhaustive: _AssetSnapshotCoverage extends never
  ? true
  : _AssetSnapshotCoverage = true
void _assetSnapshotExhaustive

// PassTarget
type DroppedPassTargetKeys = never
type MappedPassTargetKeys = 'criteria' | 'target_value' | 'violated'
type _PassTargetCoverage = Exclude<
  keyof PassTargetDto,
  MappedPassTargetKeys | DroppedPassTargetKeys
>
const _passTargetExhaustive: _PassTargetCoverage extends never
  ? true
  : _PassTargetCoverage = true
void _passTargetExhaustive

// FailingIndicator
type DroppedFailingIndicatorKeys = never
type MappedFailingIndicatorKeys = 'metric' | 'display_name' | 'value' | 'threshold'
type _FailingIndicatorCoverage = Exclude<
  keyof FailingIndicatorDto,
  MappedFailingIndicatorKeys | DroppedFailingIndicatorKeys
>
const _failingIndicatorExhaustive: _FailingIndicatorCoverage extends never
  ? true
  : _FailingIndicatorCoverage = true
void _failingIndicatorExhaustive

// SliMetadata
type DroppedSliMetadataKeys = never
type MappedSliMetadataKeys =
  | 'mode'
  | 'expected_samples'
  | 'actual_samples'
  | 'missing_pct'
  | 'chunks_failed'
type _SliMetadataCoverage = Exclude<
  keyof SliMetadataDto,
  MappedSliMetadataKeys | DroppedSliMetadataKeys
>
const _sliMetadataExhaustive: _SliMetadataCoverage extends never
  ? true
  : _SliMetadataCoverage = true
void _sliMetadataExhaustive

// TrendPoint
type DroppedTrendPointKeys = never
type MappedTrendPointKeys =
  | 'timestamp'
  | 'value'
  | 'score'
  | 'eval_id'
  | 'result'
  | 'baseline'
  | 'evaluation_name'
  | 'targets'
type _TrendPointCoverage = Exclude<
  keyof TrendPointDto,
  MappedTrendPointKeys | DroppedTrendPointKeys
>
const _trendPointExhaustive: _TrendPointCoverage extends never
  ? true
  : _TrendPointCoverage = true
void _trendPointExhaustive

// TrendTargets
type DroppedTrendTargetsKeys = never
type MappedTrendTargetsKeys = 'pass' | 'warn'
type _TrendTargetsCoverage = Exclude<
  keyof TrendTargetsDto,
  MappedTrendTargetsKeys | DroppedTrendTargetsKeys
>
const _trendTargetsExhaustive: _TrendTargetsCoverage extends never
  ? true
  : _TrendTargetsCoverage = true
void _trendTargetsExhaustive

// TrendTargetEntry
type DroppedTrendTargetEntryKeys = never
type MappedTrendTargetEntryKeys = 'criteria' | 'target_value' | 'violated'
type _TrendTargetEntryCoverage = Exclude<
  keyof TrendTargetEntryDto,
  MappedTrendTargetEntryKeys | DroppedTrendTargetEntryKeys
>
const _trendTargetEntryExhaustive: _TrendTargetEntryCoverage extends never
  ? true
  : _TrendTargetEntryCoverage = true
void _trendTargetEntryExhaustive

// EvaluationNameEntry
type DroppedEvaluationNameEntryKeys = never
type MappedEvaluationNameEntryKeys = 'name' | 'count' | 'last_run'
type _EvaluationNameEntryCoverage = Exclude<
  keyof EvaluationNameEntryDto,
  MappedEvaluationNameEntryKeys | DroppedEvaluationNameEntryKeys
>
const _evaluationNameEntryExhaustive: _EvaluationNameEntryCoverage extends never
  ? true
  : _EvaluationNameEntryCoverage = true
void _evaluationNameEntryExhaustive

// ReEvalResultItem
type DroppedReEvalResultItemKeys = never
type MappedReEvalResultItemKeys =
  | 'id'
  | 'evaluation_name'
  | 'period_start'
  | 'period_end'
  | 'old_result'
  | 'new_result'
  | 'old_score'
  | 'new_score'
type _ReEvalResultItemCoverage = Exclude<
  keyof ReEvalResultItemDto,
  MappedReEvalResultItemKeys | DroppedReEvalResultItemKeys
>
const _reEvalResultItemExhaustive: _ReEvalResultItemCoverage extends never
  ? true
  : _ReEvalResultItemCoverage = true
void _reEvalResultItemExhaustive

// ReEvaluateResponse
type DroppedReEvaluateResponseKeys = never
type MappedReEvaluateResponseKeys =
  | 'affected_evaluations'
  | 'slo_version_used'
  | 'results'
type _ReEvaluateResponseCoverage = Exclude<
  keyof ReEvaluateResponseDto,
  MappedReEvaluateResponseKeys | DroppedReEvaluateResponseKeys
>
const _reEvaluateResponseExhaustive: _ReEvaluateResponseCoverage extends never
  ? true
  : _ReEvaluateResponseCoverage = true
void _reEvaluateResponseExhaustive

// --- Stub functions (implemented in tasks 5-9) ----------------------------

/* eslint-disable @typescript-eslint/no-unused-vars -- filled in by Task 5+ */
export function dtoToEvaluationSummary(dto: EvaluationSummaryDto): Evaluation {
  return {
    id: dto.id,
    evaluationId: dto.evaluation_id,
    evaluationName: dto.evaluation_name,
    status: dto.status,
    outcome: collapseOutcome(dto.result, dto.invalidated),
    score: dto.score,
    period: makeDateRange(dto.period_start, dto.period_end),
    sloName: dto.slo_name,
    sloVersion: dto.slo_version,
    sliName: dto.sli_name,
    sliVersion: dto.sli_version,
    dataSourceName: dto.data_source_name,
    ingestionMode: dto.ingestion_mode,
    adapterUsed: dto.adapter_used,
    invalidated: dto.invalidated,
    originalOutcome: dto.original_result == null ? null : normalizeOutcome(dto.original_result),
    originalScore: dto.original_score ?? null,
    overrideReason: dto.override_reason ?? null,
    overrideAuthor: dto.override_author ?? null,
    assetSnapshot: dtoToAssetSnapshot(dto.asset_snapshot),
    variables: dto.variables ?? {},
    baselinePin: dtoToBaselinePin(dto),
    latestAnnotation: dto.latest_annotation ? dtoToAnnotation(dto.latest_annotation) : null,
    annotationCount: dto.annotation_count ?? 0,
    createdAt: new Date(dto.created_at),
    topFailures: (dto.top_failures ?? []).map(dtoToFailingIndicator),
  }
}

export function dtoToEvaluationDetail(dto: EvaluationDetailDto): EvaluationDetail {
  const summary = dtoToEvaluationSummary(dto)
  const sliMetadata: Record<string, SliMetadata> = {}
  for (const [key, value] of Object.entries(dto.sli_metadata ?? {})) {
    sliMetadata[key] = dtoToSliMetadata(value)
  }
  return {
    ...summary,
    invalidationNote: dto.invalidation_note ?? null,
    comparedEvaluationIds: dto.compared_evaluation_ids ?? [],
    annotations: (dto.annotations ?? []).map(dtoToAnnotation),
    indicators: (dto.indicator_results ?? []).map(dtoToIndicator),
    totalScorePassThreshold: dto.total_score_pass_threshold ?? null,
    totalScoreWarningThreshold: dto.total_score_warning_threshold ?? null,
    sliMetadata,
  }
}

export function dtoToEvaluationList(dto: {
  items: EvaluationSummaryDto[]
  total: number
  truncated: boolean
}): EvaluationList {
  return {
    items: dto.items.map(dtoToEvaluationSummary),
    total: dto.total,
    truncated: dto.truncated,
  }
}

export function dtoToIndicator(_dto: IndicatorResultDto): Indicator {
  throw new Error('dtoToIndicator: not yet implemented (Task 6)')
}

export function dtoToAnnotation(_dto: AnnotationDto): Annotation {
  throw new Error('dtoToAnnotation: not yet implemented (Task 6)')
}

export function dtoToTrendPoint(_dto: TrendPointDto): TrendPoint {
  throw new Error('dtoToTrendPoint: not yet implemented (Task 7)')
}

export function dtoToEvaluationNameEntry(
  _dto: EvaluationNameEntryDto,
): EvaluationNameEntry {
  throw new Error('dtoToEvaluationNameEntry: not yet implemented (Task 7)')
}

export function dtoToReEvaluateResponse(
  _dto: ReEvaluateResponseDto,
): ReEvaluateResponse {
  throw new Error('dtoToReEvaluateResponse: not yet implemented (Task 8)')
}

export function triggerEvaluationInputToDto(
  _input: TriggerEvaluationInput,
): EvaluateSingleRequestDto {
  throw new Error('triggerEvaluationInputToDto: not yet implemented (Task 9)')
}

export function reEvaluateInputToDto(_input: ReEvaluateInput): ReEvaluateRequestDto {
  throw new Error('reEvaluateInputToDto: not yet implemented (Task 9)')
}

export function overrideStatusInputToDto(
  _input: OverrideStatusInput,
): OverrideStatusRequestDto {
  throw new Error('overrideStatusInputToDto: not yet implemented (Task 9)')
}
/* eslint-enable @typescript-eslint/no-unused-vars */
