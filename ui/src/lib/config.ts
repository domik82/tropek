interface UIConfig {
  maxEvaluations: number
  pageSize: number
}

const DEFAULTS: UIConfig = {
  maxEvaluations: 1000,
  pageSize: 200,
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
