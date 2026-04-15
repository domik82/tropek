export type SloScopeOutcome = 'pass' | 'warning' | 'fail' | 'invalidated' | 'error'

export interface SloScopeOption {
  sloName: string
  displayName: string
  sloEvaluationId: string
  currentResult: SloScopeOutcome
}

export type SloScopeFilter = 'all' | 'invalidated-only' | 'not-invalidated'

export type SloScopeInitialMode = 'all' | { singleSlo: string }

export interface SloScopeResult {
  availableSlos: SloScopeOption[]
  selected: Set<string>
  setSelected: (next: Set<string>) => void
  reset: () => void
  lookupEvalId: (sloName: string) => string | undefined
}
