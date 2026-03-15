// src/lib/theme-utils.ts
// Pure utility functions for the theme system — no React or DOM imports.

export const FONT_MIN = 12
export const FONT_MAX = 18

export function clampFontSize(n: number): number {
  return Math.max(FONT_MIN, Math.min(FONT_MAX, n))
}
