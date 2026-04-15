import type { SloScopeResult } from './types'

interface Props {
  scope: SloScopeResult
  onOpenPicker: () => void
}

export function SloScopeField({ scope, onOpenPicker }: Props) {
  const total = scope.availableSlos.length
  const selectedCount = scope.selected.size
  const isPartial = selectedCount !== total

  return (
    <div className='flex items-center gap-2 px-3 py-2 rounded-md bg-muted/30 border border-border text-xs'>
      <span className='text-muted-foreground shrink-0'>Applies to:</span>
      <button
        type='button'
        onClick={onOpenPicker}
        aria-label='Change scope'
        className={`flex-1 text-left font-medium ${
          isPartial ? 'text-primary' : 'text-foreground'
        } hover:underline`}
      >
        {selectedCount} of {total} SLO{total === 1 ? '' : 's'}
        {isPartial && <span className='ml-2 text-muted-foreground'>(partial)</span>}
      </button>
      {isPartial && (
        <button
          type='button'
          onClick={scope.reset}
          aria-label='Reset to all SLOs'
          className='text-xs text-muted-foreground hover:text-foreground px-2 py-0.5 rounded border border-border'
        >
          Reset
        </button>
      )}
    </div>
  )
}
