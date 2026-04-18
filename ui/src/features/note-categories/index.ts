export type {
  CategoryColor,
  NoteCategory,
  NoteCategoryInput,
  NoteCategoryPatch,
} from './domain'
export { paletteOf, PALETTE_OPTIONS } from './palette'
export {
  useNoteCategories,
  useCreateNoteCategory,
  useUpdateNoteCategory,
  useDeleteNoteCategory,
} from './hooks'
