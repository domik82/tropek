import { describe, it, expect } from 'vitest'
import { dtoToAsset, type AssetDto } from './mappers'

describe('dtoToAsset', () => {
  it('maps a minimal DTO into a domain Asset', () => {
    const dto: AssetDto = {
      id: 'id-1',
      name: 'svc',
      display_name: 'Service One',
      type_name: 'service',
      tags: { env: 'prod' },
      variables: {},
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-02T00:00:00Z',
    }
    const asset = dtoToAsset(dto)
    expect(asset.id).toBe('id-1')
    expect(asset.name).toBe('svc')
    expect(asset.displayName).toBe('Service One')
    expect(asset.typeName).toBe('service')
    expect(asset.tags).toEqual({ env: 'prod' })
    expect(asset.createdAt).toBeInstanceOf(Date)
    expect(asset.updatedAt).toBeInstanceOf(Date)
    expect(asset.heatmapConfig).toBeNull()
  })
})
