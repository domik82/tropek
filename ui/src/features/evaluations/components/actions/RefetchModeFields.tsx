import { Input } from '@/components/ui/input'
import type { RefetchResponse } from '../../domain'

interface Props {
  fromDate: string
  onFromDateChange: (value: string) => void
  toDate: string
  onToDateChange: (value: string) => void
  onlyFailed: boolean
  onOnlyFailedChange: (value: boolean) => void
  confirmed: boolean
  onConfirmedChange: (value: boolean) => void
  preview: RefetchResponse | undefined
  previewLoading: boolean
  previewError: Error | null
}

const CHECKBOX_CLASSES = 'rounded border-border accent-[var(--entity-sli)]'

function PreviewLine({ preview, previewLoading, previewError, fromDate, toDate }: Pick<Props, 'preview' | 'previewLoading' | 'previewError' | 'fromDate' | 'toDate'>) {
  if (previewError) {
    return <p className='text-xs text-fail'>{previewError.message}</p>
  }
  if (!preview) {
    return <p className='text-xs text-muted-foreground'>{previewLoading ? 'Checking…' : 'Nothing to refetch'}</p>
  }
  if (preview.refetched === 0) {
    return <p className='text-xs text-muted-foreground'>Nothing to refetch</p>
  }
  return (
    <p className='text-xs text-foreground'>
      Will refetch {preview.refetched} of {preview.matched} SLO evaluations between {fromDate} and {toDate}
    </p>
  )
}

export function RefetchModeFields({
  fromDate,
  onFromDateChange,
  toDate,
  onToDateChange,
  onlyFailed,
  onOnlyFailedChange,
  confirmed,
  onConfirmedChange,
  preview,
  previewLoading,
  previewError,
}: Props) {
  return (
    <>
      <div>
        <label htmlFor='refetch-from' className='block text-xs text-muted-foreground mb-1'>
          Start date (UTC)
        </label>
        <Input id='refetch-from' type='datetime-local' value={fromDate} onChange={e => onFromDateChange(e.target.value)} />
      </div>
      <div>
        <label htmlFor='refetch-to' className='block text-xs text-muted-foreground mb-1'>
          End date (UTC)
        </label>
        <Input id='refetch-to' type='datetime-local' value={toDate} onChange={e => onToDateChange(e.target.value)} />
      </div>
      <label className='flex items-center gap-2 text-sm text-foreground cursor-pointer'>
        <input
          type='checkbox'
          checked={onlyFailed}
          onChange={e => onOnlyFailedChange(e.target.checked)}
          className={CHECKBOX_CLASSES}
        />
        Only SLO evaluations that failed
      </label>
      <p className='text-xs text-fail bg-fail/10 border border-fail/20 rounded px-3 py-2'>
        Stored values, SLI samples and change points for the selected SLOs between these dates are deleted and fetched
        again from the source. If the source no longer holds this period, the data cannot be recovered without a
        database restore.
      </p>
      <PreviewLine
        preview={preview}
        previewLoading={previewLoading}
        previewError={previewError}
        fromDate={fromDate}
        toDate={toDate}
      />
      <label className='flex items-center gap-2 text-sm text-foreground cursor-pointer'>
        <input
          type='checkbox'
          checked={confirmed}
          onChange={e => onConfirmedChange(e.target.checked)}
          className={CHECKBOX_CLASSES}
        />
        I understand that the stored data for this period is deleted
      </label>
    </>
  )
}
