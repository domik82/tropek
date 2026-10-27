import { useMemo, useState } from 'react'
import { getConfig } from '@/lib/config'
import { useDebouncedValue } from '@/lib/useDebouncedValue'
import { useRefetch, useRefetchPreview } from '../../hooks'
import type { RefetchResponse } from '../../domain'

export function utcInputToIso(utcInputValue: string): string | null {
  if (!utcInputValue) return null
  // Refetch-mode dates are UTC: the callers prefill them from UTC server timestamps.
  // Appending Z parses both the HH:mm and the HH:mm:ss forms a datetime-local value can take.
  const parsed = new Date(`${utcInputValue}Z`)
  return Number.isNaN(parsed.getTime()) ? null : parsed.toISOString()
}

interface PreviewQuery {
  data: RefetchResponse | undefined
  /** True while a preview request runs or the debounce has not yet passed the latest input on to it. */
  isLoading: boolean
  error: Error | null
}

export interface RefetchFormState {
  fromDate: string
  setFromDate: (value: string) => void
  toDate: string
  setToDate: (value: string) => void
  onlyFailed: boolean
  setOnlyFailed: (value: boolean) => void
  deletionAcknowledged: boolean
  setDeletionAcknowledged: (value: boolean) => void
  previewQuery: PreviewQuery
  canConfirm: boolean
  submit: () => Promise<void>
  isPending: boolean
  error: Error | null
}

interface RefetchFormParams {
  assetName: string
  evaluationName: string
  sloNames: string[]
  defaultRefetchDay?: string
  /** False while refetch mode is not shown: no input is built, so no preview is requested. */
  enabled: boolean
}

export function useRefetchForm({
  assetName,
  evaluationName,
  sloNames,
  defaultRefetchDay,
  enabled,
}: RefetchFormParams): RefetchFormState {
  const [fromDate, setFromDate] = useState(defaultRefetchDay ?? '')
  const [toDate, setToDate] = useState(defaultRefetchDay ?? '')
  const [onlyFailed, setOnlyFailed] = useState(false)
  const [acknowledgedInputKey, setAcknowledgedInputKey] = useState<string | null>(null)
  const refetchMutation = useRefetch()

  const sloNamesKey = sloNames.join('\u0000')
  const fromIso = utcInputToIso(fromDate)
  const toIso = utcInputToIso(toDate)
  const refetchInput = useMemo(
    () =>
      enabled && fromIso && toIso && sloNamesKey
        ? {
            assetName,
            evaluationName,
            sloNames: sloNamesKey.split('\u0000'),
            from: fromIso,
            to: toIso,
            onlyFailed,
            reason: null,
          }
        : null,
    [enabled, assetName, evaluationName, sloNamesKey, fromIso, toIso, onlyFailed],
  )
  // The acknowledgement is bound to the exact period/scope it was given for; any change invalidates it.
  const refetchInputKey = JSON.stringify(refetchInput)
  const deletionAcknowledged = refetchInput !== null && acknowledgedInputKey === refetchInputKey
  const debouncedInput = useDebouncedValue(refetchInput, getConfig().refetchPreviewDebounceMs)
  const previewResult = useRefetchPreview(debouncedInput)

  const canConfirm =
    deletionAcknowledged &&
    refetchInput !== null &&
    refetchInput === debouncedInput &&
    (previewResult.data?.refetched ?? 0) > 0

  const submit = async () => {
    if (!canConfirm || refetchInput === null) throw new Error('refetch is not confirmable yet')
    await refetchMutation.mutateAsync({ ...refetchInput, dryRun: false })
  }

  return {
    fromDate,
    setFromDate,
    toDate,
    setToDate,
    onlyFailed,
    setOnlyFailed,
    deletionAcknowledged,
    setDeletionAcknowledged: checked => setAcknowledgedInputKey(checked ? refetchInputKey : null),
    previewQuery: {
      data: previewResult.data,
      isLoading: previewResult.isFetching || refetchInput !== debouncedInput,
      error: previewResult.error,
    },
    canConfirm,
    submit,
    isPending: refetchMutation.isPending,
    error: refetchMutation.error,
  }
}
