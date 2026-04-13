// src/features/evaluations/components/TriggerEvaluationModal.tsx
// Modal form for triggering a new evaluation.
// Cross-feature: imports useAssets from features/assets.

import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { triggerEvaluation } from '../api'
import { useAssets } from '@/features/assets/hooks'
import { evaluationKeys } from '@/lib/queryKeys'

const schema = z.object({
  asset_name: z.string().min(1, 'Required'),
  eval_name: z.string().min(1, 'Required'),
  period_start: z.string().min(1, 'Required'),
  period_end: z.string().min(1, 'Required'),
})
type FormValues = z.infer<typeof schema>

interface Props {
  open: boolean
  onClose: () => void
}

export function TriggerEvaluationModal({ open, onClose }: Props) {
  const qc = useQueryClient()
  const { data: assets } = useAssets()

  const { register, handleSubmit, reset, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(schema),
  })

  const trigger = useMutation({
    mutationFn: triggerEvaluation,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: evaluationKeys.all })
      reset()
      onClose()
    },
  })

  function onSubmit(values: FormValues) {
    trigger.mutate({
      assetName: values.asset_name,
      evalName: values.eval_name,
      period: {
        from: new Date(values.period_start).toISOString(),
        to: new Date(values.period_end).toISOString(),
      },
      variables: {},
    })
  }

  const assetNames = assets?.map(a => a.name) ?? []

  return (
    <Dialog open={open} onOpenChange={v => !v && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Trigger Evaluation</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-3 pt-2">
          <div>
            <label className="text-xs text-muted-foreground">Asset</label>
            <select {...register('asset_name')} className="w-full mt-1 bg-surface-sunken border border-border rounded px-3 py-2 text-sm">
              <option value="">Select asset...</option>
              {assetNames.map(n => <option key={n} value={n}>{n}</option>)}
            </select>
            {errors.asset_name && <p className="text-destructive-form-text text-xs mt-1">{errors.asset_name.message}</p>}
          </div>
          <div>
            <label className="text-xs text-muted-foreground">Evaluation Name</label>
            <Input {...register('eval_name')} placeholder="e.g. perf-test-linux" className="mt-1" />
            {errors.eval_name && <p className="text-destructive-form-text text-xs mt-1">{errors.eval_name.message}</p>}
          </div>
          <div className="flex gap-2">
            <div className="flex-1">
              <label className="text-xs text-muted-foreground">Start</label>
              <Input {...register('period_start')} type="datetime-local" className="mt-1" />
            </div>
            <div className="flex-1">
              <label className="text-xs text-muted-foreground">End</label>
              <Input {...register('period_end')} type="datetime-local" className="mt-1" />
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={trigger.isPending}>
              {trigger.isPending ? 'Triggering...' : 'Trigger'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
