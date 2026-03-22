export type Operator = '<' | '<=' | '>' | '>=' | '='
export type Sign = '+' | '-'

export interface CriteriaParts {
  operator: Operator
  sign: Sign | null
  value: number
  percent: boolean
}

const OPERATORS: Operator[] = ['<=', '>=', '<', '>', '=']

export function parseCriteria(raw: string): CriteriaParts | null {
  const s = raw.trim()
  if (!s) return null

  let operator: Operator | null = null
  let rest = s
  for (const op of OPERATORS) {
    if (s.startsWith(op)) {
      operator = op
      rest = s.slice(op.length)
      break
    }
  }
  if (!operator) return null

  let sign: Sign | null = null
  if (rest.startsWith('+')) {
    sign = '+'
    rest = rest.slice(1)
  } else if (rest.startsWith('-')) {
    sign = '-'
    rest = rest.slice(1)
  }

  const percent = rest.endsWith('%')
  if (percent) rest = rest.slice(0, -1)

  const value = parseFloat(rest)
  if (isNaN(value)) return null

  return { operator, sign, value, percent }
}

export const DEFAULT_CRITERIA: CriteriaParts = {
  operator: '<',
  sign: null,
  value: 0,
  percent: false,
}

export function serializeCriteria(parts: CriteriaParts): string {
  const sign = parts.sign ?? ''
  const pct = parts.percent ? '%' : ''
  return `${parts.operator}${sign}${parts.value}${pct}`
}
