import type { components } from '@/generated/api'
import type {
  MethodCriteriaOverride,
  Slo,
  SloAssignment,
  SloComparisonConfig,
  SloGroupAssignment,
  SloObjective,
  SloValidationObjective,
  SloValidationResult,
} from './domain'

export type SloDto = components['schemas']['SLODefinitionRead']
export type SloObjectiveDto = components['schemas']['SLOObjectiveRead']
export type SloObjectiveInDto = components['schemas']['SLOObjectiveIn']
export type SloComparisonConfigDto = components['schemas']['ComparisonConfig']
export type MethodCriteriaOverrideDto = components['schemas']['MethodCriteriaOverride']
export type SloAssignmentDto = components['schemas']['SLOAssignmentRead']
export type SloGroupAssignmentDto = components['schemas']['SLOGroupAssignmentRead']
export type SloValidationResultDto = components['schemas']['SLOValidationResult']

// --- Slo -------------------------------------------------------------------

// Placeholder for DTO fields intentionally not surfaced in the domain type.
// Add entries as `'field_name'` union members, each with a comment explaining why.
type DroppedSloKeys = never

type MappedSloKeys =
  | 'id'
  | 'name'
  | 'version'
  | 'comparable_from_version'
  | 'display_name'
  | 'author'
  | 'notes'
  | 'tags'
  | 'variables'
  | 'kind'
  | 'sli_definition_id'
  | 'sli_name'
  | 'sli_version'
  | 'created_at'
  | 'active'
  | 'objectives'
  | 'total_score_pass_threshold'
  | 'total_score_warning_threshold'
  | 'comparison'
  | 'method_criteria'

// Compile-time check: every non-dropped DTO key must be mapped. If TypeScript
// errors here with a string literal type, the generated DTO has a new field —
// add it to `MappedSloKeys` and map it in `dtoToSlo`, or add it to
// `DroppedSloKeys` with a comment explaining why the UI ignores it.
type _SloCoverage = Exclude<keyof SloDto, MappedSloKeys | DroppedSloKeys>
const _sloExhaustive: _SloCoverage extends never ? true : _SloCoverage = true
void _sloExhaustive

// --- SloObjective ----------------------------------------------------------

type DroppedSloObjectiveKeys =
  | 'change_point' // per-objective CP detection config — not surfaced in SLO detail UI yet

type MappedSloObjectiveKeys =
  | 'sli'
  | 'display_name'
  | 'pass_threshold'
  | 'warning_threshold'
  | 'weight'
  | 'key_sli'
  | 'sort_order'

type _SloObjectiveCoverage = Exclude<
  keyof SloObjectiveDto,
  MappedSloObjectiveKeys | DroppedSloObjectiveKeys
>
const _sloObjectiveExhaustive: _SloObjectiveCoverage extends never
  ? true
  : _SloObjectiveCoverage = true
void _sloObjectiveExhaustive

// --- SloAssignment ---------------------------------------------------------

type DroppedSloAssignmentKeys = never

type MappedSloAssignmentKeys =
  | 'id'
  | 'asset_id'
  | 'asset_group_id'
  | 'slo_definition_id'
  | 'slo_name'
  | 'slo_version'
  | 'data_source_id'
  | 'data_source_name'
  | 'comparison_rules'
  | 'created_at'

type _SloAssignmentCoverage = Exclude<
  keyof SloAssignmentDto,
  MappedSloAssignmentKeys | DroppedSloAssignmentKeys
>
const _sloAssignmentExhaustive: _SloAssignmentCoverage extends never
  ? true
  : _SloAssignmentCoverage = true
void _sloAssignmentExhaustive

// --- SloGroupAssignment ----------------------------------------------------

type DroppedSloGroupAssignmentKeys = never

type MappedSloGroupAssignmentKeys =
  | 'id'
  | 'asset_id'
  | 'asset_group_id'
  | 'slo_group_id'
  | 'slo_group_name'
  | 'data_source_id'
  | 'data_source_name'
  | 'created_at'

type _SloGroupAssignmentCoverage = Exclude<
  keyof SloGroupAssignmentDto,
  MappedSloGroupAssignmentKeys | DroppedSloGroupAssignmentKeys
>
const _sloGroupAssignmentExhaustive: _SloGroupAssignmentCoverage extends never
  ? true
  : _SloGroupAssignmentCoverage = true
void _sloGroupAssignmentExhaustive

// --- Mappers ---------------------------------------------------------------

export function dtoToComparison(
  dto: SloComparisonConfigDto | null | undefined,
): SloComparisonConfig {
  if (!dto) return {}
  return {
    compareWith: dto.compare_with ?? undefined,
    includeResultWithScore: dto.include_result_with_score ?? undefined,
    numberOfComparisonResults: dto.number_of_comparison_results ?? undefined,
    aggregateFunction: (dto.aggregate_function as SloComparisonConfig['aggregateFunction']) ?? undefined,
    scopeTags: dto.scope_tags ?? undefined,
  }
}

export function dtoToMethodCriteriaOverride(
  dto: MethodCriteriaOverrideDto,
): MethodCriteriaOverride {
  return {
    method: dto.method ?? undefined,
    aggregation: dto.aggregation ?? undefined,
    passThreshold: dto.pass_threshold ?? undefined,
    warningThreshold: dto.warning_threshold ?? undefined,
    weight: dto.weight ?? undefined,
    keySli: dto.key_sli ?? undefined,
  }
}

export function dtoToMethodCriteria(
  dto: { [key: string]: MethodCriteriaOverrideDto } | null | undefined,
): Record<string, MethodCriteriaOverride> | null {
  if (!dto) return null
  const out: Record<string, MethodCriteriaOverride> = {}
  for (const [key, value] of Object.entries(dto)) {
    out[key] = dtoToMethodCriteriaOverride(value)
  }
  return out
}

export function dtoToObjective(dto: SloObjectiveDto): SloObjective {
  return {
    sli: dto.sli,
    displayName: dto.display_name,
    passThreshold: dto.pass_threshold ?? [],
    warningThreshold: dto.warning_threshold ?? [],
    weight: dto.weight,
    keySli: dto.key_sli,
    sortOrder: dto.sort_order,
  }
}

function dtoToValidationObjective(dto: SloObjectiveInDto): SloValidationObjective {
  return {
    sli: dto.sli,
    displayName: dto.display_name,
    passThreshold: dto.pass_threshold ?? [],
    warningThreshold: dto.warning_threshold ?? [],
    weight: dto.weight,
    keySli: dto.key_sli,
  }
}

export function dtoToSlo(dto: SloDto): Slo {
  return {
    id: dto.id,
    name: dto.name,
    version: dto.version,
    comparableFromVersion: dto.comparable_from_version,
    displayName: dto.display_name,
    author: dto.author,
    notes: dto.notes,
    // Backend guarantees string values; OpenAPI widens to unknown in some generators.
    tags: dto.tags as Record<string, string>,
    variables: dto.variables as Record<string, string>,
    // Backend enum is currently typed as `string`; narrow to the UI's closed union.
    kind: dto.kind as 'standard' | 'template',
    sliDefinitionId: dto.sli_definition_id,
    sliName: dto.sli_name ?? null,
    sliVersion: dto.sli_version ?? null,
    createdAt: new Date(dto.created_at),
    active: dto.active,
    objectives: dto.objectives.map(dtoToObjective),
    totalScorePassThreshold: dto.total_score_pass_threshold,
    totalScoreWarningThreshold: dto.total_score_warning_threshold,
    comparison: dtoToComparison(dto.comparison as SloComparisonConfigDto),
    methodCriteria: dtoToMethodCriteria(dto.method_criteria),
  }
}

export function dtoToSloAssignment(dto: SloAssignmentDto): SloAssignment {
  return {
    id: dto.id,
    assetId: dto.asset_id,
    assetGroupId: dto.asset_group_id,
    sloDefinitionId: dto.slo_definition_id,
    sloName: dto.slo_name,
    sloVersion: dto.slo_version,
    dataSourceId: dto.data_source_id,
    dataSourceName: dto.data_source_name,
    comparisonRules: dto.comparison_rules,
    createdAt: new Date(dto.created_at),
  }
}

export function dtoToSloGroupAssignment(dto: SloGroupAssignmentDto): SloGroupAssignment {
  return {
    id: dto.id,
    assetId: dto.asset_id,
    assetGroupId: dto.asset_group_id,
    sloGroupId: dto.slo_group_id,
    sloGroupName: dto.slo_group_name,
    dataSourceId: dto.data_source_id,
    dataSourceName: dto.data_source_name,
    createdAt: new Date(dto.created_at),
  }
}

export function dtoToSloValidationResult(dto: SloValidationResultDto): SloValidationResult {
  return {
    valid: dto.valid,
    errors: dto.errors.map((error) => ({ field: error.field, message: error.message })),
    objectives: dto.objectives
      ? dto.objectives.map(dtoToValidationObjective)
      : undefined,
  }
}
