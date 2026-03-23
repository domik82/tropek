import { useMemo } from 'react'
import { useQueries } from '@tanstack/react-query'
import { groupKeys } from '@/lib/queryKeys'
import { fetchGroupSloLinks } from '@/features/slos/api'
import type { MinLink } from './useRegistryTree'

export function useAllGroupLinks(groupNames: string[]) {
  const filtered = useMemo(
    () => groupNames.filter(n => n !== '__ungrouped__'),
    [groupNames],
  )

  const linkQueries = useQueries({
    queries: filtered.map(name => ({
      queryKey: groupKeys.links(name),
      queryFn: () => fetchGroupSloLinks(name),
    })),
  })

  return useMemo(() => {
    const flat: MinLink[] = []
    const byGroup: Record<string, MinLink[]> = {}
    for (let i = 0; i < filtered.length; i++) {
      const data = linkQueries[i]?.data ?? []
      const links: MinLink[] = data.map(l => ({
        slo_name: l.slo_name,
        sli_name: l.sli_name,
        data_source_name: l.data_source_name,
      }))
      byGroup[filtered[i]] = links
      flat.push(...links)
    }
    const seen = new Set<string>()
    const unique = flat.filter(l => {
      const key = `${l.slo_name}|${l.sli_name}|${l.data_source_name}`
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
    return { allLinks: unique, groupLinksMap: byGroup }
  }, [filtered, linkQueries])
}
