import type { components } from '@/generated/api'
import type { CategoryColor, NoteCategory, NoteCategoryInput, NoteCategoryPatch } from './domain'

type NoteCategoryDto = components['schemas']['AnnotationCategoryRead']
type NoteCategoryCreateDto = components['schemas']['AnnotationCategoryCreate']
type NoteCategoryUpdateDto = components['schemas']['AnnotationCategoryUpdate']

export function dtoToNoteCategory(dto: NoteCategoryDto): NoteCategory {
  return {
    id: dto.id,
    name: dto.name,
    label: dto.label,
    color: dto.color as CategoryColor,
    showOnGraph: dto.show_on_graph,
    isSystem: dto.is_system,
    createdAt: new Date(dto.created_at),
    updatedAt: dto.updated_at ? new Date(dto.updated_at) : null,
  }
}

export function noteCategoryInputToDto(input: NoteCategoryInput): NoteCategoryCreateDto {
  return {
    name: input.name,
    label: input.label,
    color: input.color,
    show_on_graph: input.showOnGraph,
  }
}

export function noteCategoryPatchToDto(patch: NoteCategoryPatch): NoteCategoryUpdateDto {
  return {
    name: patch.name,
    label: patch.label,
    color: patch.color,
    show_on_graph: patch.showOnGraph,
  }
}
