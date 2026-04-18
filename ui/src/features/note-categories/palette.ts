import type { CategoryColor } from './domain'

const PALETTE: Record<CategoryColor, { bg: string; fg: string }> = {
  sky: { bg: 'var(--color-category-sky-bg)', fg: 'var(--color-category-sky-fg)' },
  green: { bg: 'var(--color-category-green-bg)', fg: 'var(--color-category-green-fg)' },
  amber: { bg: 'var(--color-category-amber-bg)', fg: 'var(--color-category-amber-fg)' },
  red: { bg: 'var(--color-category-red-bg)', fg: 'var(--color-category-red-fg)' },
  purple: { bg: 'var(--color-category-purple-bg)', fg: 'var(--color-category-purple-fg)' },
  pink: { bg: 'var(--color-category-pink-bg)', fg: 'var(--color-category-pink-fg)' },
  slate: { bg: 'var(--color-category-slate-bg)', fg: 'var(--color-category-slate-fg)' },
  gray: { bg: 'var(--color-category-gray-bg)', fg: 'var(--color-category-gray-fg)' },
}

export function paletteOf(color: CategoryColor): { bg: string; fg: string } {
  return PALETTE[color]
}

export const DEFAULT_CATEGORY_COLOR: CategoryColor = 'sky'

export const DEFAULT_CATEGORY_PALETTE = PALETTE[DEFAULT_CATEGORY_COLOR]

export const PALETTE_OPTIONS: CategoryColor[] = [
  'sky',
  'green',
  'amber',
  'red',
  'purple',
  'pink',
  'slate',
  'gray',
]
