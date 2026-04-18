import { describe, it, expect } from 'vitest'
import {
  dtoToNoteCategory,
  noteCategoryInputToDto,
  noteCategoryPatchToDto,
} from './mappers'

describe('note-category mappers', () => {
  it('maps DTO to domain and parses dates', () => {
    const d = dtoToNoteCategory({
      id: 'a',
      name: 'info',
      label: 'Info',
      color: 'sky',
      show_on_graph: true,
      is_system: false,
      created_at: '2026-04-16T10:00:00Z',
      updated_at: null,
    })
    expect(d).toMatchObject({ name: 'info', showOnGraph: true, isSystem: false })
    expect(d.createdAt).toBeInstanceOf(Date)
    expect(d.updatedAt).toBeNull()
  })

  it('maps input to DTO using snake_case', () => {
    expect(
      noteCategoryInputToDto({
        name: 'x',
        label: 'X',
        color: 'sky',
        showOnGraph: false,
      }),
    ).toEqual({ name: 'x', label: 'X', color: 'sky', show_on_graph: false })
  })

  it('maps patch preserving unset keys as undefined', () => {
    expect(noteCategoryPatchToDto({ label: 'Y' })).toEqual({
      name: undefined,
      label: 'Y',
      color: undefined,
      show_on_graph: undefined,
    })
  })
})
