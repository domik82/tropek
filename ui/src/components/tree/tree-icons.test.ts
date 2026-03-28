import { describe, it, expect } from 'vitest'
import { Server, Component, Database, Container, Laptop, Gauge, CircuitBoard, ShieldCheck, Braces, Folder, LayoutGrid } from 'lucide-react'
import { getAssetTypeIcon, getEntityIcon, FALLBACK_ASSET_ICON } from './tree-icons'

describe('getAssetTypeIcon', () => {
  it('maps vm to Server', () => { expect(getAssetTypeIcon('vm')).toBe(Server) })
  it('maps service to Component', () => { expect(getAssetTypeIcon('service')).toBe(Component) })
  it('maps database to Database', () => { expect(getAssetTypeIcon('database')).toBe(Database) })
  it('maps container to Container', () => { expect(getAssetTypeIcon('container')).toBe(Container) })
  it('maps endpoint to Laptop', () => { expect(getAssetTypeIcon('endpoint')).toBe(Laptop) })
  it('maps load-test to Gauge', () => { expect(getAssetTypeIcon('load-test')).toBe(Gauge) })
  it('returns CircuitBoard for unknown types', () => { expect(getAssetTypeIcon('unknown')).toBe(CircuitBoard) })
  it('exports FALLBACK_ASSET_ICON as CircuitBoard', () => { expect(FALLBACK_ASSET_ICON).toBe(CircuitBoard) })
})

describe('getEntityIcon', () => {
  it('maps slo to ShieldCheck', () => { expect(getEntityIcon('slo')).toBe(ShieldCheck) })
  it('maps sli to Braces', () => { expect(getEntityIcon('sli')).toBe(Braces) })
  it('maps datasource to Database', () => { expect(getEntityIcon('datasource')).toBe(Database) })
  it('maps group to Folder', () => { expect(getEntityIcon('group')).toBe(Folder) })
  it('maps all to LayoutGrid', () => { expect(getEntityIcon('all')).toBe(LayoutGrid) })
})
