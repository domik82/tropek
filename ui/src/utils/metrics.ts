/**
 * Compute the relative percentage change between a current value and a baseline.
 *
 * When baseline is non-zero: standard (value - baseline) / |baseline| * 100
 * When baseline is zero:     treat denominator as 1, so the change equals value * 100
 *                            (0 → 2 = +200%, 0 → 0 = 0%)
 * When baseline is null:     no comparison available, returns null
 */
export function computeChangePct(value: number, baseline: number | null): number | null {
  if (baseline === null) return null
  const denominator = baseline === 0 ? 1 : Math.abs(baseline)
  return +((value - baseline) / denominator * 100).toFixed(2)
}

/**
 * For a relative criteria string like "<=+10%" or "<=+20%", compute the
 * per-point threshold value from each point's baseline.
 *
 * Returns null for points that have no baseline yet (first few evaluations
 * before a rolling window can be established).
 *
 * Returns an empty array if the criteria is not a recognised relative format.
 */
export function computeRelativeThresholdSeries(
  data: { baseline?: number | null }[],
  criteria: string,
): (number | null)[] {
  const m = criteria.match(/^<=\+(\d+(?:\.\d+)?)%$/)
  if (!m) return []
  const multiplier = 1 + parseFloat(m[1]) / 100
  return data.map(p => p.baseline != null ? +(p.baseline * multiplier).toFixed(3) : null)
}
