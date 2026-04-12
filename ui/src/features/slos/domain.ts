// Domain types for the slos feature. UI vocabulary; camelCase;
// Date objects rather than ISO strings. Hand-written — never regenerated.

export interface MethodCriteriaOverride {
  method?: string
  aggregation?: string
  passThreshold?: string[]
  warningThreshold?: string[]
  weight?: number
  keySli?: boolean
}

export interface SloObjective {
  sli: string
  displayName: string
  passThreshold: string[]
  warningThreshold: string[]
  weight: number
  keySli: boolean
  sortOrder: number
}

export interface SloComparisonConfig {
  compareWith?: string
  includeResultWithScore?: string
  numberOfComparisonResults?: number
  aggregateFunction?: string
  scopeTags?: string[]
}

export interface Slo {
  id: string
  name: string
  version: number
  comparableFromVersion: number
  displayName: string | null
  author: string | null
  notes: string | null
  tags: Record<string, string>
  variables: Record<string, string>
  kind: 'standard' | 'template'
  sliDefinitionId: string | null
  sliName: string | null
  sliVersion: number | null
  createdAt: Date
  active: boolean
  objectives: SloObjective[]
  totalScorePassThreshold: number
  totalScoreWarningThreshold: number
  comparison: SloComparisonConfig
  methodCriteria: Record<string, MethodCriteriaOverride> | null
}

export interface SloValidationError {
  field: string
  message: string
}

// Validation-result objectives lack sort_order (they round-trip SLOObjectiveIn, not SLOObjectiveRead).
export interface SloValidationObjective {
  sli: string
  displayName: string
  passThreshold: string[]
  warningThreshold: string[]
  weight: number
  keySli: boolean
}

export interface SloValidationResult {
  valid: boolean
  errors: SloValidationError[]
  objectives?: SloValidationObjective[]
}

export interface SloAssignment {
  id: string
  assetId: string | null
  assetGroupId: string | null
  sloDefinitionId: string
  sloName: string
  sloVersion: number
  dataSourceId: string
  dataSourceName: string
  comparisonRules: Record<string, unknown>[] | null
  createdAt: Date
}

export interface SloGroupAssignment {
  id: string
  assetId: string | null
  assetGroupId: string | null
  sloGroupId: string
  sloGroupName: string
  dataSourceId: string
  dataSourceName: string
  createdAt: Date
}
