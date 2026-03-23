import { describe, it, expect } from 'vitest'
import type { Asset } from './types'

/**
 * Contract tests — verify TypeScript types match the API response shape.
 * If these fail after a backend rename, the UI types need updating too.
 */
describe('Asset type contract', () => {
  it('Asset type has tags field (not labels)', () => {
    // This is a compile-time + runtime check.
    // If Asset.tags doesn't exist, TypeScript will error AND this test fails.
    const asset: Asset = {
      id: 'test',
      name: 'test',
      type_name: 'service',
      tags: { env: 'prod' },
      variables: {},
      created_at: '2025-01-01',
      updated_at: '2025-01-01',
    }
    expect(asset.tags).toBeDefined()
    expect(asset.variables).toBeDefined()
    expect((asset as unknown as Record<string, unknown>).labels).toBeUndefined()
  })
})
