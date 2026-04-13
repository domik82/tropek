// DateRange is stored as ISO-8601 UTC strings, not Date objects. This is a
// deliberate narrow exception to the "real Date objects in domain layer" rule
// of the DTO/domain/mapper pattern — see features/navigator/domain.ts (commit
// ce34376) for the navigator precedent and the reasoning:
//
//   period.from doubles as a Map key (EvaluationHeatmap.tsx) and as an ECharts
//   x-axis label, where Date object identity would break equality.
//
// Consumers that need Date semantics parse from `from`/`to` at the call site.

export interface DateRange {
  from: string
  to: string
}

export function makeDateRange(from: string, to: string): DateRange {
  return { from, to }
}
