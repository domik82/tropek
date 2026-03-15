// src/lib/types.ts

export interface PagedResponse<T> {
  items: T[]
  total: number
}
