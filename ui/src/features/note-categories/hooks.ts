import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as api from './api'
import type { NoteCategoryInput, NoteCategoryPatch } from './domain'

const QK = { all: ['note-categories'] as const }

export function useNoteCategories() {
  return useQuery({
    queryKey: QK.all,
    queryFn: api.listNoteCategories,
    staleTime: 5 * 60_000,
  })
}

export function useCreateNoteCategory() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: NoteCategoryInput) => api.createNoteCategory(input),
    onSuccess: () => qc.invalidateQueries({ queryKey: QK.all }),
  })
}

export function useUpdateNoteCategory() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (args: { id: string; patch: NoteCategoryPatch }) =>
      api.updateNoteCategory(args.id, args.patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: QK.all }),
  })
}

export function useDeleteNoteCategory() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.deleteNoteCategory(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: QK.all }),
  })
}
