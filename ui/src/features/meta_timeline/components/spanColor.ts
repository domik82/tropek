export const META_SPAN_PALETTE_SIZE = 8

export function getSpanColorIndex(value: string): number {
  let hash = 5381
  for (let i = 0; i < value.length; i++) {
    hash = ((hash << 5) + hash + value.charCodeAt(i)) | 0
  }
  return Math.abs(hash) % META_SPAN_PALETTE_SIZE
}
