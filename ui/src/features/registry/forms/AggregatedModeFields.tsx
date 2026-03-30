import { AGGREGATION_METHODS, METHOD_LABELS, INTERVAL_PRESETS } from '@/lib/aggregation-methods'
import { Input } from '@/components/ui/input'

interface AggregatedModeFieldsProps {
  queryTemplate: string
  interval: string
  methods: string[]
  onQueryTemplateChange: (value: string) => void
  onIntervalChange: (value: string) => void
  onMethodsChange: (methods: string[]) => void
}

export function AggregatedModeFields({
  queryTemplate,
  interval,
  methods,
  onQueryTemplateChange,
  onIntervalChange,
  onMethodsChange,
}: AggregatedModeFieldsProps) {
  function toggleMethod(method: string) {
    if (methods.includes(method)) {
      onMethodsChange(methods.filter(m => m !== method))
    } else {
      onMethodsChange([...methods, method])
    }
  }

  return (
    <div className="space-y-3">
      {/* Query Template */}
      <div>
        <label htmlFor="sli-query-template" className="block text-xs text-muted-foreground mb-1">
          Query Template
        </label>
        <Input
          id="sli-query-template"
          value={queryTemplate}
          onChange={e => onQueryTemplateChange(e.target.value)}
          placeholder="rate(metric{job=&quot;$job&quot;}[$interval])"
          className="font-mono text-xs"
        />
        <p className="text-[10px] text-muted-foreground mt-0.5">
          Use $variable placeholders. $interval is reserved for the step value.
        </p>
      </div>

      {/* Interval */}
      <div>
        <label htmlFor="sli-interval" className="block text-xs text-muted-foreground mb-1">
          Interval
        </label>
        <div className="flex items-center gap-2">
          <Input
            id="sli-interval"
            value={interval}
            onChange={e => onIntervalChange(e.target.value)}
            placeholder="1m"
            className="w-20 font-mono text-xs"
          />
          <div className="flex gap-1">
            {INTERVAL_PRESETS.map(preset => (
              <button
                key={preset}
                type="button"
                onClick={() => onIntervalChange(preset)}
                className={`px-2 py-0.5 text-xs rounded border transition-colors ${
                  interval === preset
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-border text-muted-foreground hover:text-foreground'
                }`}
              >
                {preset}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Methods */}
      <div>
        <span className="block text-xs text-muted-foreground mb-1">Aggregation Methods</span>
        <div className="flex flex-wrap gap-x-4 gap-y-1.5">
          {AGGREGATION_METHODS.map(method => (
            <label key={method} className="inline-flex items-center gap-1.5 text-xs cursor-pointer">
              <input
                type="checkbox"
                checked={methods.includes(method)}
                onChange={() => toggleMethod(method)}
                aria-label={METHOD_LABELS[method]}
              />
              <span className="text-foreground">{METHOD_LABELS[method]}</span>
            </label>
          ))}
        </div>
      </div>
    </div>
  )
}
