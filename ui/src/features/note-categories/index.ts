export type {
  CategoryColor,
  NoteCategory,
  NoteCategoryInput,
  NoteCategoryPatch,
} from './domain'
export {
  paletteOf,
  PALETTE_OPTIONS,
  DEFAULT_CATEGORY_COLOR,
  DEFAULT_CATEGORY_PALETTE,
} from './palette'
export {
  useNoteCategories,
  useCreateNoteCategory,
  useUpdateNoteCategory,
  useDeleteNoteCategory,
} from './hooks'
