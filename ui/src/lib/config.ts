interface UIConfig {
  maxEvaluations: number
  pageSize: number
  heatmapSloGroupsExpandedByDefault: boolean
  /** Day count above which the date picker shows a performance warning. */
  heatmapSlowThresholdDays: number
  /** Earliest date with data in the DB (ISO date string, e.g. "2024-01-01"). */
  dataStartDate: string
  /** Pixels before the viewport at which a lazy trend group starts fetching. */
  trendPrefetchMarginPx: number
  /**
   * Quiet time after the last refetch-form edit before the dry-run preview is requested.
   * UI-side default only: not served by /api/config/ui, like heatmapSlowThresholdDays.
   */
  refetchPreviewDebounceMs: number
}

const DEFAULTS: UIConfig = {
  maxEvaluations: 5000,
  pageSize: 200,
  heatmapSloGroupsExpandedByDefault: true,
  heatmapSlowThresholdDays: 30,
  dataStartDate: '2024-01-01',
  trendPrefetchMarginPx: 200,
  refetchPreviewDebounceMs: 400,
}

let config: UIConfig = DEFAULTS

export async function loadConfig(): Promise<void> {
  try {
    const res = await fetch('/api/config/ui')
    if (res.ok) {
      const json = await res.json()
      config = { ...DEFAULTS, ...json }
    }
  } catch {
    // Use defaults if API is unreachable
  }
}

export function getConfig(): UIConfig {
  return config
}
