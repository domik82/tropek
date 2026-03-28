import type { LucideIcon } from 'lucide-react'
import {
  Server, Component, Database, Container, Laptop, Gauge, CircuitBoard,
  ShieldCheck, Braces, Folder, LayoutGrid,
} from 'lucide-react'

const ASSET_TYPE_ICONS: Record<string, LucideIcon> = {
  vm: Server,
  service: Component,
  database: Database,
  container: Container,
  endpoint: Laptop,
  'load-test': Gauge,
}

export const FALLBACK_ASSET_ICON: LucideIcon = CircuitBoard

const ENTITY_ICONS: Record<string, LucideIcon> = {
  slo: ShieldCheck,
  sli: Braces,
  datasource: Database,
  group: Folder,
  all: LayoutGrid,
}

export function getAssetTypeIcon(typeName: string): LucideIcon {
  return ASSET_TYPE_ICONS[typeName] ?? FALLBACK_ASSET_ICON
}

export function getEntityIcon(entityType: string): LucideIcon {
  return ENTITY_ICONS[entityType] ?? FALLBACK_ASSET_ICON
}
