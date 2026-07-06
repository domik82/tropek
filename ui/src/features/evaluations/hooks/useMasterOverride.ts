import { useState } from 'react'

/**
 * Resolve a per-instance preference against a shared master value.
 *
 * Returns `[effective, setOverride]` where `effective = override ?? master`.
 * `override` starts as `null` ("follow master"). Calling `setOverride(value)`
 * pins this instance to `value`; when `generation` changes (i.e. the master was
 * toggled) the override resets to `null`, so every instance re-syncs to master.
 *
 * The reset runs during render (React's "adjust state when a prop changes"
 * pattern) rather than in an effect, so the cleared value takes effect on the
 * same render — no transient frame where a stale override lingers.
 */
export function useMasterOverride<T>(master: T, generation: number): [T, (value: T) => void] {
  const [override, setOverride] = useState<T | null>(null)
  const [lastGeneration, setLastGeneration] = useState(generation)

  if (generation !== lastGeneration) {
    setLastGeneration(generation)
    setOverride(null)
  }

  const effective = override ?? master
  return [effective, setOverride as (value: T) => void]
}
