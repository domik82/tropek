export type ChangePointStatus = 'unprocessed' | 'acknowledged' | 'hidden'
export type ChangePointDirection = 'regression' | 'improvement'

export interface ChangePoint {
  id: string
  assetId: string
  sloName: string
  metricName: string
  periodStart: Date
  direction: ChangePointDirection
  changeRelativePct: number
  changeAbsolute: number
  preSegmentMean: number
  postSegmentMean: number
  pvalue: number
  status: ChangePointStatus
  triageAuthor: string | null
  triageNote: string | null
  triageAt: Date | null
  linkedTicket: string | null
  foundByEvaluationId: string | null
  createdAt: Date
}

export interface ChangePointFilters {
  status?: ChangePointStatus
  direction?: ChangePointDirection
  assetId?: string
  sloName?: string
  metric?: string
  limit?: number
  offset?: number
}

export interface TriageInput {
  status: 'acknowledged' | 'hidden'
  triageAuthor?: string
  triageNote?: string
}

export interface BulkTriageInput {
  ids: string[]
  status: 'acknowledged' | 'hidden'
  triageAuthor?: string
  triageNote?: string
}
