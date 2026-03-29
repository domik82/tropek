// src/features/evaluations/components/TriggerEvaluationModal.tsx
// Modal form for triggering a new evaluation.
// Cross-feature: imports useAssetGroups from features/assets and useSlos from features/slos.

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
import { useAssetGroups } from '@/features/assets/hooks'
import { useSlos } from '@/features/slos/hooks'
import { evaluationKeys } from '@/lib/queryKeys'

const schema = z.object({
  group_name: z.string().min(1, 'Required'),
  evaluation_name: z.string().min(1, 'Required'),
  slo_name: z.string().min(1, 'Required'),
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
  const { data: assetGroups } = useAssetGroups()
  const { data: slos } = useSlos()

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
    trigger.mutate(values)
  }

  const groupNames = assetGroups?.top_level.map(g => g.name) ?? []
  const sloNames = slos?.map(s => s.name) ?? []

  return (
    <Dialog open={open} onOpenChange={v => !v && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Trigger Evaluation</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-3 pt-2">
          <div>
            <label className="text-xs text-muted-foreground">Asset Group</label>
            <select {...register('group_name')} className="w-full mt-1 bg-surface-sunken border border-border rounded px-3 py-2 text-sm">
              <option value="">Select group...</option>
              {groupNames.map(n => <option key={n} value={n}>{n}</option>)}
            </select>
            {errors.group_name && <p className="text-destructive-form-text text-xs mt-1">{errors.group_name.message}</p>}
          </div>
          <div>
            <label className="text-xs text-muted-foreground">Evaluation Name</label>
            <Input {...register('evaluation_name')} placeholder="e.g. perf-test-linux" className="mt-1" />
            {errors.evaluation_name && <p className="text-destructive-form-text text-xs mt-1">{errors.evaluation_name.message}</p>}
          </div>
          <div>
            <label className="text-xs text-muted-foreground">SLO</label>
            <select {...register('slo_name')} className="w-full mt-1 bg-surface-sunken border border-border rounded px-3 py-2 text-sm">
              <option value="">Select SLO...</option>
              {sloNames.map(n => <option key={n} value={n}>{n}</option>)}
            </select>
            {errors.slo_name && <p className="text-destructive-form-text text-xs mt-1">{errors.slo_name.message}</p>}
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
