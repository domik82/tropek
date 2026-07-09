/**
 * Return a copy of the search params with `from`/`to` moved to the end (from before to),
 * so the time range is always the last two params — easy to find and hand-edit in the URL.
 * Params without `from`/`to` are returned in their original order.
 */
export function withTimeParamsLast(search: URLSearchParams): URLSearchParams {
  const from = search.get('from')
  const to = search.get('to')
  const ordered = new URLSearchParams()
  for (const [key, value] of search) {
    if (key === 'from' || key === 'to') continue
    ordered.append(key, value)
  }
  if (from !== null) ordered.set('from', from)
  if (to !== null) ordered.set('to', to)
  return ordered
}
