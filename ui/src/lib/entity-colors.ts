export const ENTITY_COLORS = {
  slo: '#7dc540',
  sli: '#A371F7',
  ds: '#58A6FF',
  group: '#8B949E',
} as const

/** Colors keyed by NodeType for tree rendering */
export const NODE_TYPE_COLORS: Record<string, string> = {
  slo: ENTITY_COLORS.slo,
  sli: ENTITY_COLORS.sli,
  datasource: ENTITY_COLORS.ds,
  group: ENTITY_COLORS.group,
  asset: '#c9d1d9',
  binding: ENTITY_COLORS.slo,
}
