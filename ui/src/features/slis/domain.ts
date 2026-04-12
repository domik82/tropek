// Domain types for the slis feature. UI vocabulary; camelCase;
// Date objects rather than ISO strings. Hand-written — never regenerated.

export interface Sli {
  id: string
  name: string
  displayName: string | null
  adapterType: string
  version: number
  comparableFromVersion: number
  indicators: Record<string, string>
  mode: 'raw' | 'aggregated'
  queryTemplate: string | null
  interval: string | null
  methods: string[] | null
  notes: string | null
  author: string | null
  tags: Record<string, string>
  active: boolean
  createdAt: Date
}
