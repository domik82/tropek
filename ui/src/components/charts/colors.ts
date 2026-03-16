/**
 * Generate a deterministic, visually distinct color for chart series.
 *
 * Uses OKLCH color space with golden-angle hue distribution to maximize
 * visual separation between adjacent indices. Varies lightness and chroma
 * in a secondary cycle to avoid the "too many similar greens" problem.
 */
export function generateSeriesColor(index: number): string {
  const hue = (index * 137.508) % 360

  const cycle = index % 3
  const lightness = cycle === 0 ? 65 : cycle === 1 ? 50 : 75
  const chroma = cycle === 0 ? 0.15 : cycle === 1 ? 0.2 : 0.12

  return `oklch(${lightness}% ${chroma} ${hue})`
}

/**
 * Build a stable color map for a sorted list of metric names.
 * The color is determined by sorted position, not by toggle state or pagination.
 */
export function buildColorMap(
  metrics: Array<{ metric: string }>,
): Map<string, string> {
  const sorted = [...metrics].sort((a, b) => a.metric.localeCompare(b.metric))
  const map = new Map<string, string>()
  for (let i = 0; i < sorted.length; i++) {
    map.set(sorted[i].metric, generateSeriesColor(i))
  }
  return map
}
