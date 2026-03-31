export const ENTITY_COLORS = {
  slo: 'var(--entity-slo)',
  sli: 'var(--entity-sli)',
  ds: 'var(--entity-datasource)',
  group: 'var(--entity-group)',
  template: '#F0B429',
  sloGroup: '#8B949E',
} as const

/** Colors keyed by NodeType for tree rendering */
export const NODE_TYPE_COLORS: Record<string, string> = {
  slo: ENTITY_COLORS.slo,
  sli: ENTITY_COLORS.sli,
  datasource: ENTITY_COLORS.ds,
  group: ENTITY_COLORS.group,
  asset: 'var(--entity-asset)',
  binding: ENTITY_COLORS.slo,
  template: ENTITY_COLORS.template,
  'slo-group': ENTITY_COLORS.sloGroup,
}

export const GROUP_PALETTE = [
  '#6897BB', '#E8915A', '#A371F7', '#7DC540', '#F85149',
  '#58A6FF', '#D4A032', '#2DD4A0', '#DB61A2', '#8B949E',
] as const
