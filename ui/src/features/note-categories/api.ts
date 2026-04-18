import type { components } from '@/generated/api'
import type { NoteCategory, NoteCategoryInput, NoteCategoryPatch } from './domain'
import {
  dtoToNoteCategory,
  noteCategoryInputToDto,
  noteCategoryPatchToDto,
} from './mappers'

type NoteCategoryDto = components['schemas']['AnnotationCategoryRead']

const BASE = '/api'

export async function listNoteCategories(): Promise<NoteCategory[]> {
  const res = await fetch(`${BASE}/note-categories`)
  if (!res.ok) throw new Error(`listNoteCategories: ${res.status}`)
  const rows: NoteCategoryDto[] = await res.json()
  return rows.map(dtoToNoteCategory)
}

export async function createNoteCategory(input: NoteCategoryInput): Promise<NoteCategory> {
  const res = await fetch(`${BASE}/note-categories`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(noteCategoryInputToDto(input)),
  })
  if (!res.ok) throw new Error(`createNoteCategory: ${res.status}`)
  return dtoToNoteCategory(await res.json())
}

export async function updateNoteCategory(
  id: string,
  patch: NoteCategoryPatch,
): Promise<NoteCategory> {
  const res = await fetch(`${BASE}/note-categories/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(noteCategoryPatchToDto(patch)),
  })
  if (!res.ok) throw new Error(`updateNoteCategory: ${res.status}`)
  return dtoToNoteCategory(await res.json())
}

export async function deleteNoteCategory(id: string): Promise<{ reassigned: number }> {
  const res = await fetch(`${BASE}/note-categories/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`deleteNoteCategory: ${res.status}`)
  return { reassigned: Number(res.headers.get('X-Reassigned-Annotations') ?? '0') }
}
