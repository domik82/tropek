// Domain types for the slo-groups feature. UI vocabulary; camelCase;
// Date objects rather than ISO strings. Hand-written — never regenerated.

export interface SloGroup {
  id: string
  name: string
  displayName: string | null
  templateSloName: string
  templateSloVersion: number
  genVariables: Record<string, string[]>
  tags: Record<string, string>
  author: string | null
  version: number
  active: boolean
  createdAt: Date
  updatedAt: Date
  generatedSloCount: number
}
