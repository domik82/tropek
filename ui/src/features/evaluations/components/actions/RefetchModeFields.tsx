import { useId } from 'react'
import { Input } from '@/components/ui/input'
import type { RefetchResponse } from '../../domain'
import type { RefetchFormState } from './useRefetchForm'

interface Props {
  form: RefetchFormState
}

const CHECKBOX_CLASSES = 'rounded border-border accent-[var(--entity-sli)]'

interface PreviewLineProps {
  preview: RefetchResponse | undefined
  previewLoading: boolean
  previewError: Error | null
  fromDate: string
  toDate: string
}

function PreviewLine({ preview, previewLoading, previewError, fromDate, toDate }: PreviewLineProps) {
  if (previewError) {
    return <p className='text-xs text-fail'>{previewError.message}</p>
  }
  if (!fromDate || !toDate) {
    return <p className='text-xs text-muted-foreground'>Pick a start and end date</p>
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

export function RefetchModeFields({ form }: Props) {
  const fromId = useId()
  const toId = useId()
  return (
    <>
      <div>
        <label htmlFor={fromId} className='block text-xs text-muted-foreground mb-1'>
          Start date (UTC)
        </label>
        <Input
          id={fromId}
          type='datetime-local'
          value={form.fromDate}
          onChange={event => form.setFromDate(event.target.value)}
        />
      </div>
      <div>
        <label htmlFor={toId} className='block text-xs text-muted-foreground mb-1'>
          End date (UTC)
        </label>
        <Input
          id={toId}
          type='datetime-local'
          value={form.toDate}
          onChange={event => form.setToDate(event.target.value)}
        />
      </div>
      <label className='flex items-center gap-2 text-sm text-foreground cursor-pointer'>
        <input
          type='checkbox'
          checked={form.onlyFailed}
          onChange={event => form.setOnlyFailed(event.target.checked)}
          className={CHECKBOX_CLASSES}
        />
        Only SLO evaluations that failed
      </label>
      <p className='text-xs text-fail bg-fail/10 border border-fail/20 rounded px-3 py-2'>
        Stored values and SLI samples of the selected SLOs between these dates are deleted and fetched again from the
        source, together with this evaluation's untriaged change points of those SLOs on those days (triaged change
        points are kept). If the source no longer holds this period, the data cannot be recovered without a
        database restore.
      </p>
      <PreviewLine
        preview={form.previewQuery.data}
        previewLoading={form.previewQuery.isLoading}
        previewError={form.previewQuery.error}
        fromDate={form.fromDate}
        toDate={form.toDate}
      />
      <label className='flex items-center gap-2 text-sm text-foreground cursor-pointer'>
        <input
          type='checkbox'
          checked={form.deletionAcknowledged}
          onChange={event => form.setDeletionAcknowledged(event.target.checked)}
          className={CHECKBOX_CLASSES}
        />
        I understand that the stored data for this period is deleted
      </label>
    </>
  )
}
