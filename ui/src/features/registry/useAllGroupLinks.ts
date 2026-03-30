import { useMemo } from 'react'
import { useQueries } from '@tanstack/react-query'
import { groupKeys } from '@/lib/queryKeys'
import { fetchGroupSloBindings } from '@/features/slos'
import type { MinBinding } from './useRegistryTree'

export function useAllGroupLinks(groupNames: string[]) {
  const filtered = useMemo(
    () => groupNames.filter(n => n !== '__ungrouped__'),
    [groupNames],
  )

  const bindingQueries = useQueries({
    queries: filtered.map(name => ({
      queryKey: groupKeys.bindings(name),
      queryFn: () => fetchGroupSloBindings(name),
    })),
  })

  return useMemo(() => {
    const flat: MinBinding[] = []
    const byGroup: Record<string, MinBinding[]> = {}
    for (let i = 0; i < filtered.length; i++) {
      const data = bindingQueries[i]?.data ?? []
      const bindings: MinBinding[] = data.map(b => ({
        slo_name: b.slo_name,
        data_source_name: b.data_source_name,
      }))
      byGroup[filtered[i]] = bindings
      flat.push(...bindings)
    }
    const seen = new Set<string>()
    const unique = flat.filter(b => {
      const key = `${b.slo_name}|${b.data_source_name}`
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
    return { allBindings: unique, groupBindingsMap: byGroup }
  }, [filtered, bindingQueries])
}
