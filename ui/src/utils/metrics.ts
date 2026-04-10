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
